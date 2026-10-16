"""Offline tests for scripts/verify/release_target_guard.py (no network, fake clients)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "verify"))
from release_target_guard import UnsafeTarget, classify, verify_live  # noqa: E402

ATLAS = "mongodb+srv://aayna_test_app:pw%40x@aayna-dev.ab1cd.mongodb.net/?retryWrites=true"
LOCAL = "mongodb://127.0.0.1:27017"


class FakeAdmin:
    def __init__(self, c):
        self.c = c

    def command(self, name, **kw):
        return self.c.responses[name]


class FakeClient:
    def __init__(self, dbs=(), hosts=None, users=None, privileges=None, ferret=False):
        self.dbs = list(dbs)
        self.admin = FakeAdmin(self)
        self.responses = {
            "buildInfo": {"version": "8.0.4", **({"ferretdbVersion": "v1.24.0"} if ferret else {})},
            "hello": {"setName": "atlas-xyz-shard-0",
                      "hosts": hosts if hosts is not None else ["ac-q1-shard-00-00.ab1cd.mongodb.net:27017",
                                                                 "ac-q1-shard-00-01.ab1cd.mongodb.net:27017"]},
            "connectionStatus": {"authInfo": {
                "authenticatedUsers": users if users is not None else [{"user": "aayna_test_app", "db": "admin"}],
                "authenticatedUserRoles": [{"role": "readWrite", "db": "aayna_release_test"}],
                "authenticatedUserPrivileges": privileges if privileges is not None else [
                    {"resource": {"db": "aayna_release_test", "collection": ""},
                     "actions": ["find", "insert", "update", "remove", "dropCollection", "createIndex"]},
                ]}},
        }

    def list_database_names(self):
        return self.dbs


@pytest.mark.parametrize("url,db", [
    (LOCAL, "test_database"), (LOCAL, "aayna_dev"), (LOCAL, "aayna_test"), (LOCAL, "aayna_prod"),
    (LOCAL, "aayna_staging"), (LOCAL, "admin"), (ATLAS, "test_database"), (ATLAS, "aayna_dev"),
    (LOCAL, "aayna_release_test"),            # Atlas DB name on a local instance
    (LOCAL, "my_test_db"),                    # contains "test" but not allowlisted
    (ATLAS, "aayna_pytest"),                  # local DB name on Atlas
    ("mongodb+srv://aayna_test_app:p@cluster0.ab1cd.mongodb.net/", "aayna_release_test"),   # wrong cluster
    ("mongodb+srv://admin:p@aayna-dev.ab1cd.mongodb.net/", "aayna_release_test"),           # wrong user
    ("mongodb+srv://aayna_test_app:p@aayna-dev.evil.example.com/", "aayna_release_test"),   # not Atlas
    ("mongodb://aayna_test_app:p@10.0.0.5:27017/", "aayna_release_test"),                   # non-srv remote
    ("mongodb://h1:27017,localhost:27017/", "aayna_pytest"),                                 # mixed hosts
    ("", "aayna_pytest"),
])
def test_static_refusals(url, db):
    with pytest.raises(UnsafeTarget):
        classify(url, db)


def test_static_allowed():
    assert classify(LOCAL, "aayna_pytest")["kind"] == "local"
    assert classify("mongodb://localhost/", "aayna_pytest")["kind"] == "local"
    info = classify(ATLAS, "aayna_release_test")
    assert info["kind"] == "atlas" and info["cluster"] == "aayna-dev"


def test_live_atlas_ok():
    info = verify_live(FakeClient(dbs=["aayna_release_test"]), ATLAS, "aayna_release_test")
    assert info["official_mongodb"] and info["write_privileges_outside_test_db"] == "none"
    assert info["roles"] == ["readWrite@aayna_release_test"]


def test_live_atlas_refuses_write_elsewhere():
    privs = [{"resource": {"db": "aayna_release_test", "collection": ""}, "actions": ["insert"]},
             {"resource": {"db": "test_database", "collection": ""}, "actions": ["find", "insert"]}]
    with pytest.raises(UnsafeTarget, match="can change data outside"):
        verify_live(FakeClient(privileges=privs), ATLAS, "aayna_release_test")


def test_live_atlas_refuses_any_db_write():
    privs = [{"resource": {"db": "", "collection": ""}, "actions": ["find", "update"]}]
    with pytest.raises(UnsafeTarget):
        verify_live(FakeClient(privileges=privs), ATLAS, "aayna_release_test")


def test_live_atlas_refuses_cluster_admin_action():
    privs = [{"resource": {"cluster": True}, "actions": ["dropDatabase", "serverStatus"]}]
    with pytest.raises(UnsafeTarget):
        verify_live(FakeClient(privileges=privs), ATLAS, "aayna_release_test")


def test_live_atlas_allows_read_only_elsewhere():
    privs = [{"resource": {"db": "aayna_release_test", "collection": ""}, "actions": ["insert"]},
             {"resource": {"cluster": True}, "actions": ["listDatabases", "serverStatus"]}]
    verify_live(FakeClient(privileges=privs), ATLAS, "aayna_release_test")


def test_live_atlas_refuses_other_user():
    with pytest.raises(UnsafeTarget, match="solely"):
        verify_live(FakeClient(users=[{"user": "atlasAdmin", "db": "admin"}]), ATLAS, "aayna_release_test")


def test_live_atlas_refuses_members_on_other_domain():
    with pytest.raises(UnsafeTarget, match="not part of the approved"):
        verify_live(FakeClient(hosts=["ac-q1-shard-00-00.zz999.mongodb.net:27017"]), ATLAS, "aayna_release_test")


def test_live_local_refuses_shared_instance():
    with pytest.raises(UnsafeTarget, match="real data"):
        verify_live(FakeClient(dbs=["aayna_pytest", "test_database"]), LOCAL, "aayna_pytest")


def test_live_reports_emulator():
    info = verify_live(FakeClient(dbs=[], ferret=True), LOCAL, "aayna_pytest")
    assert info["official_mongodb"] is False
