/* 资讯 · 个人情报台 — 交互层（无依赖） */
(function () {
  'use strict';

  var root = document.documentElement;

  /* ---------- 主题 ---------- */
  var KEY = 'zixun-theme';
  function applyTheme(t) {
    root.setAttribute('data-theme', t);
    var b = document.getElementById('theme-btn');
    if (b) b.textContent = t === 'dark' ? '☀' : '☾';
  }
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  if (!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) saved = 'dark';
  var q = new URLSearchParams(location.search).get('theme');
  applyTheme(q === 'dark' || q === 'light' ? q : (saved || 'light'));

  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('#theme-btn');
    if (t) {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem(KEY, next); } catch (e2) {}
    }
    var c = e.target.closest && e.target.closest('#copy-btn');
    if (c) {
      var url = location.href;
      if (navigator.clipboard) navigator.clipboard.writeText(url);
      var old = c.textContent;
      c.textContent = '已复制';
      setTimeout(function () { c.textContent = old; }, 1400);
    }
  });

  /* ---------- 阅读进度 ---------- */
  var bar = document.querySelector('.progress');
  function onScroll() {
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var p = h > 0 ? (window.scrollY / h) * 100 : 0;
    if (bar) bar.style.width = p.toFixed(2) + '%';
    var top = document.getElementById('to-top');
    if (top) top.style.opacity = window.scrollY > 900 ? '1' : '0';
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- 目录高亮 ---------- */
  var links = Array.prototype.slice.call(document.querySelectorAll('.nav a[href^="#"]'));
  var targets = links.map(function (a) { return document.querySelector(a.getAttribute('href')); });
  if ('IntersectionObserver' in window && targets.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var i = targets.indexOf(en.target);
        if (i < 0) return;
        links.forEach(function (l) { l.classList.remove('active'); });
        links[i].classList.add('active');
        if (links[i].scrollIntoView) {
          links[i].scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
        }
      });
    }, { rootMargin: '-15% 0px -70% 0px', threshold: 0 });
    targets.forEach(function (t) { if (t) io.observe(t); });
  }

  /* ---------- 键盘翻页 ---------- */
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    var prev = document.body.getAttribute('data-prev');
    var next = document.body.getAttribute('data-next');
    if (e.key === 'ArrowLeft' && prev) location.href = prev;
    if (e.key === 'ArrowRight' && next) location.href = next;
  });
})();
