"""Offline tests for scripts/verify/release_target_guard.py (no network, fake clients)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "verify"))
from release_target_guard import UnsafeTarget, classify, verify_live  # noqa: E402

RW = ["find", "insert", "update", "remove", "listCollections", "listIndexes", "createIndex", "dropIndex",
      "createCollection", "dropCollection", "collStats", "dbStats", "killCursors"]
ATLAS = "mongodb+srv://aayna_test_app:pw%40x@aayna-dev.gzn5qto.mongodb.net/?retryWrites=true"
LOCAL = "mongodb://127.0.0.1:27017"


class FakeAdmin:
    def __init__(self, c):
        self.c = c

    def command(self, name, **kw):
        return self.c.responses[name]


class FakeClient:
    def __init__(self, dbs=(), hosts=None, users=None, privileges=None, ferret=False, roles=None):
        self.dbs = list(dbs)
        self.admin = FakeAdmin(self)
        self.responses = {
            "buildInfo": {"version": "8.0.4", **({"ferretdbVersion": "v1.24.0"} if ferret else {})},
            "hello": {"setName": "atlas-xyz-shard-0",
                      "hosts": hosts if hosts is not None else ["ac-q1-shard-00-00.gzn5qto.mongodb.net:27017",
                                                                 "ac-q1-shard-00-01.gzn5qto.mongodb.net:27017"]},
            "connectionStatus": {"authInfo": {
                "authenticatedUsers": users if users is not None else [{"user": "aayna_test_app", "db": "admin"}],
                "authenticatedUserRoles": roles if roles is not None else [{"role": "readWrite", "db": "aayna_release_test"}],
                "authenticatedUserPrivileges": privileges if privileges is not None else [
                    {"resource": {"db": "aayna_release_test", "collection": ""},
                     "actions": RW},
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
    ("mongodb+srv://aayna_test_app:p@cluster0.gzn5qto.mongodb.net/", "aayna_release_test"),   # wrong cluster
    ("mongodb+srv://admin:p@aayna-dev.gzn5qto.mongodb.net/", "aayna_release_test"),           # wrong user
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
    privs = [{"resource": {"db": "aayna_release_test", "collection": ""}, "actions": RW},
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
    privs = [{"resource": {"db": "aayna_release_test", "collection": ""}, "actions": RW},
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


@pytest.mark.parametrize("host", [
    "aayna-dev.gzn5qt0.mongodb.net",                  # one character off (0 vs o)
    "aayna-dev.abcd123.mongodb.net",                  # same cluster name, another Atlas project
    "aayna-dev.gzn5qto.mongodb.net.evil.com",         # suffix attack
    "aayna-dev.gzn5qto.mongodb.net.",                 # trailing dot
    "evil.aayna-dev.gzn5qto.mongodb.net",             # extra label in front
    "xaayna-dev.gzn5qto.mongodb.net",                 # prefix lookalike
    "aayna-dev-gzn5qto.mongodb.net",                  # dash instead of dot
    "aayna_dev.gzn5qto.mongodb.net",                  # underscore lookalike
    "аayna-dev.gzn5qto.mongodb.net",             # Cyrillic 'а' homoglyph
    "aayna-dev.gzn5qto.mongodb.com",                  # wrong TLD
    "Aayna_test_app",                                 # the broken value found in the founder's file
    "localhost.gzn5qto.mongodb.net",
])
def test_lookalike_hosts_refused(host):
    with pytest.raises(UnsafeTarget, match="approved Atlas cluster|single mongodb"):
        classify(f"mongodb+srv://aayna_test_app:pw@{host}/", "aayna_release_test")


def test_userinfo_host_confusion_refused():
    # '@' inside the password must not let a different host through
    url = "mongodb+srv://aayna_test_app:p%40aayna-dev.gzn5qto.mongodb.net@evil.example.com/"
    with pytest.raises(UnsafeTarget):
        classify(url, "aayna_release_test")


def test_exact_host_case_insensitive_and_with_options():
    url = "mongodb+srv://aayna_test_app:pw@AAYNA-DEV.gzn5qto.mongodb.net/?retryWrites=true&w=majority&appName=aayna-dev"
    assert classify(url, "aayna_release_test")["host"] == "aayna-dev.gzn5qto.mongodb.net"


@pytest.mark.parametrize("member", [
    "ac-q1-shard-00-00.abcd123.mongodb.net:27017",          # other project
    "evil.ac-q1-shard-00-00.gzn5qto.mongodb.net:27017",     # extra label
    "ac-q1-shard-00-00.gzn5qto.mongodb.net.evil.com:27017", # suffix attack
])
def test_live_refuses_lookalike_members(member):
    with pytest.raises(UnsafeTarget, match="not part of the approved"):
        verify_live(FakeClient(hosts=[member]), ATLAS, "aayna_release_test")


def test_live_refuses_empty_privilege_report():
    with pytest.raises(UnsafeTarget, match="lacks"):
        verify_live(FakeClient(privileges=[]), ATLAS, "aayna_release_test")


def test_live_refuses_missing_list_collections():
    privs = [{"resource": {"db": "aayna_release_test", "collection": ""}, "actions": ["find", "insert"]}]
    with pytest.raises(UnsafeTarget, match="listCollections"):
        verify_live(FakeClient(privileges=privs), ATLAS, "aayna_release_test")


@pytest.mark.parametrize("roles", [
    [],
    [{"role": "read", "db": "aayna_release_test"}],
    [{"role": "readWrite", "db": "aayna_release_test"}, {"role": "readWrite", "db": "test_database"}],
    [{"role": "readWriteAnyDatabase", "db": "admin"}],
    [{"role": "atlasAdmin", "db": "admin"}],
])
def test_live_refuses_unexpected_roles(roles):
    with pytest.raises(UnsafeTarget, match="must hold only"):
        verify_live(FakeClient(roles=roles), ATLAS, "aayna_release_test")


def test_live_refuses_collection_scoped_role():
    # Seen on the real Atlas user (2026-10-17): readWrite limited to a collection named "All collections"
    privs = [{"resource": {"db": "aayna_release_test", "collection": "All collections"}, "actions": RW}]
    with pytest.raises(UnsafeTarget, match="leave the role's Collection field EMPTY"):
        verify_live(FakeClient(privileges=privs), ATLAS, "aayna_release_test")
