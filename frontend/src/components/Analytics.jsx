import { useEffect } from "react";
import { useLocation } from "react-router-dom";

// Public, build-time analytics IDs. Empty => the corresponding pixel is never loaded.
// Pixel IDs are public identifiers — never put secret keys here.
const GA4_ID = (process.env.REACT_APP_GA_MEASUREMENT_ID || process.env.REACT_APP_GA4_ID || "").trim();
const META_PIXEL_ID = (process.env.REACT_APP_META_PIXEL_ID || "").trim();
const TIKTOK_PIXEL_ID = (process.env.REACT_APP_TIKTOK_PIXEL_ID || "").trim();

function loadGA4(id) {
  if (window.__aaynaGA4Loaded) return;
  window.__aaynaGA4Loaded = true;
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() {
    window.dataLayer.push(arguments);
  };
  window.gtag("js", new Date());
  window.gtag("config", id, { send_page_view: false });
}

function loadMetaPixel(id) {
  if (window.__aaynaMetaLoaded) return;
  window.__aaynaMetaLoaded = true;
  /* eslint-disable */
  !(function (f, b, e, v, n, t, s) {
    if (f.fbq) return;
    n = f.fbq = function () {
      n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
    };
    if (!f._fbq) f._fbq = n;
    n.push = n;
    n.loaded = !0;
    n.version = "2.0";
    n.queue = [];
    t = b.createElement(e);
    t.async = !0;
    t.src = v;
    s = b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t, s);
  })(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
  /* eslint-enable */
  window.fbq("init", id);
}

function loadTikTok(id) {
  if (window.__aaynaTikTokLoaded) return;
  window.__aaynaTikTokLoaded = true;
  /* eslint-disable */
  !(function (w, d, t) {
    w.TiktokAnalyticsObject = t;
    var ttq = (w[t] = w[t] || []);
    ttq.methods = "page track identify instances debug on off once ready alias group enableCookie disableCookie".split(" ");
    ttq.setAndDefer = function (e, n) {
      e[n] = function () {
        e.push([n].concat(Array.prototype.slice.call(arguments, 0)));
      };
    };
    for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
    ttq.instance = function (e) {
      for (var n = ttq._i[e] || [], i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(n, ttq.methods[i]);
      return n;
    };
    ttq.load = function (e, n) {
      var r = "https://analytics.tiktok.com/i18n/pixel/events.js";
      ttq._i = ttq._i || {};
      ttq._i[e] = [];
      ttq._i[e]._u = r;
      ttq._t = ttq._t || {};
      ttq._t[e] = +new Date();
      ttq._o = ttq._o || {};
      ttq._o[e] = n || {};
      var o = d.createElement("script");
      o.type = "text/javascript";
      o.async = !0;
      o.src = r + "?sdkid=" + e + "&lib=" + t;
      var a = d.getElementsByTagName("script")[0];
      a.parentNode.insertBefore(o, a);
    };
    ttq.load(id);
  })(window, document, "ttq");
  /* eslint-enable */
}

// Loads GA4 / Meta / TikTok pixels only when their IDs are set, and NEVER on /admin routes.
export default function Analytics() {
  const { pathname } = useLocation();
  const isAdmin = pathname.startsWith("/admin");

  useEffect(() => {
    if (isAdmin) return; // never load tracking on admin dashboard
    if (GA4_ID) loadGA4(GA4_ID);
    if (META_PIXEL_ID) loadMetaPixel(META_PIXEL_ID);
    if (TIKTOK_PIXEL_ID) loadTikTok(TIKTOK_PIXEL_ID);
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) return; // never track admin page views
    if (GA4_ID && window.gtag) window.gtag("event", "page_view", { page_path: pathname });
    if (META_PIXEL_ID && window.fbq) window.fbq("track", "PageView");
    if (TIKTOK_PIXEL_ID && window.ttq) window.ttq.page();
  }, [pathname, isAdmin]);

  return null;
}
