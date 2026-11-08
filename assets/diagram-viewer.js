/*
 * 그림 크게 보기 (라이트박스 + 팬·줌)
 *
 * 본문의 mermaid 그림이나 이미지를 누르면 페이지 위에 크게 띄운다.
 * 휠로 확대·축소하고, 왼쪽 버튼으로 끌어 옮기고, 그림을 더블클릭하면 화면에 맞춘다.
 * Esc를 누르거나 그림 바깥을 누르면 닫는다. 터치 화면에서는 두 손가락으로 확대한다.
 *
 * Material 테마는 mermaid 그림을 닫힌 shadow DOM 안에 그려서 바깥에서 SVG를 꺼낼 수 없다.
 * 그래서 Material이 <pre class="mermaid">를 그림 상자(div.mermaid)로 바꿔 끼우는 순간을
 * MutationObserver로 보고 원본 소스를 기억해 두었다가, 누르면 같은 mermaid 설정으로 한 번 더 그린다.
 * 소스를 못 찾거나 다시 그리기에 실패하면 그림 상자를 통째로 옮겨 띄우고, 닫을 때 제자리에 돌려놓는다.
 */
(function () {
  "use strict";

  var MAX_SCALE = 10;
  var MARGIN = 24; // 화면에 맞출 때 그림 둘레 여백(px). 위쪽 막대 아래의 그림 영역 기준
  var MOVE_THRESHOLD = 4; // 이만큼 움직이면 클릭이 아니라 끌기로 본다(px)

  var sources = new WeakMap(); // div.mermaid → mermaid 소스
  var renderSeq = 0;

  // 0. 어두운 화면에서 안 보이는 mermaid 부분의 색을 바로잡는다.
  //
  // 테마는 mermaid@11의 최신판을 받아 쓰고, 자기 색 규칙(themeCSS)을 mermaid.initialize로 넘긴다.
  // mermaid 11에서 화살표 머리의 id가 "arrowhead"에서 "그림id-arrowhead"로 바뀌고 alt 상자의
  // 두 번째 구간 제목이 "sectionTitle"이라는 새 이름을 쓰게 되면서, 테마 규칙이 닿지 않아
  // mermaid 기본색(진한 회색·검정)이 남았다. 밝은 화면에서는 티가 안 나지만 어두운 화면에서는 묻힌다.
  // 그래서 테마가 mermaid.initialize를 부르기 전에 끼어들어 규칙 몇 줄을 덧붙인다.
  // 색은 테마 변수로 지정하므로 밝은 화면에서는 지금과 거의 같다.
  var EXTRA_THEME_CSS = [
    // 시퀀스 그림 화살표 머리: 테마가 원래 쓰려던 메시지 선 색
    'marker[id$="-arrowhead"] path { fill: var(--md-mermaid-sequence-message-line-color) !important; stroke: none !important; }',
    // 시퀀스 그림 X 머리(--x 화살표)
    'marker[id$="-crosshead"] path { stroke: var(--md-mermaid-sequence-message-line-color) !important; }',
    // alt 상자 두 번째 구간부터의 제목: 첫 구간 제목(loopText)과 같은 색
    ".sectionTitle, .sectionTitle > tspan { fill: var(--md-mermaid-sequence-loop-fg-color) !important; }",
    // ER 그림의 '0개' 동그라미: 흰색으로 칠해져 있어 어두운 화면에서 꽉 찬 점으로 보인다. 바탕색으로 비운다.
    'marker[id*="_er-zeroOr"] circle { fill: var(--md-default-bg-color) !important; }'
  ].join("\n");

  function patchMermaid(m) {
    if (!m || m.__dvPatched || typeof m.initialize !== "function") return;
    var initialize = m.initialize;
    m.initialize = function (config) {
      var merged = Object.assign({}, config);
      merged.themeCSS = (merged.themeCSS || "") + "\n" + EXTRA_THEME_CSS;
      return initialize.call(this, merged);
    };
    m.__dvPatched = true;
  }

  // 테마는 본문에 mermaid 그림이 있을 때만 <script>를 붙여 mermaid를 불러오고, 그 script의 load 이벤트를
  // 받은 뒤 initialize를 부른다. 문서 쪽 캡처 단계 리스너가 script 자신의 리스너보다 먼저 돌므로 그 사이에 바꿔 끼운다.
  patchMermaid(window.mermaid);
  document.addEventListener(
    "load",
    function (e) {
      var target = e.target;
      if (target && target.tagName === "SCRIPT" && /mermaid/.test(target.src || "")) {
        patchMermaid(window.mermaid);
      }
    },
    true
  );

  // 1. Material이 그린 그림 상자와 원본 소스를 짝짓는다.
  new MutationObserver(function (records) {
    records.forEach(function (record) {
      if (!record.addedNodes.length || !record.removedNodes.length) return;
      var pre = null;
      record.removedNodes.forEach(function (node) {
        if (node.nodeName === "PRE") pre = node;
      });
      if (!pre) return;
      record.addedNodes.forEach(function (node) {
        if (node.nodeType === 1 && node.matches("div.mermaid")) {
          sources.set(node, pre.textContent);
        }
      });
    });
  }).observe(document.documentElement, { childList: true, subtree: true });

  // 2. 보기 창
  var dialog = null;
  var stage = null;
  var zoomLabel = null;
  var canvas = null; // 지금 띄운 그림을 담은 상자
  var restore = null; // 닫을 때 할 정리(그림 상자를 옮겨 띄운 경우)
  var busy = false;
  var view = { s: 1, x: 0, y: 0, w: 1, h: 1, maxFit: 1, pageScale: 1 };

  // 가장 작게 줄일 수 있는 배율: 그림 전체가 화면에 들어가는 크기와 원래 크기(100%) 중 작은 쪽.
  // 이보다 더 줄이면 그림이 점처럼 작아질 뿐이라 막는다.
  function minScale() {
    return Math.max(0.05, Math.min(1, containScale()));
  }

  function clamp(s) {
    return Math.min(MAX_SCALE, Math.max(minScale(), s));
  }

  function apply() {
    canvas.style.transform =
      "translate(" + view.x + "px," + view.y + "px) scale(" + view.s + ")";
    zoomLabel.textContent = Math.round(view.s * 100) + "%";
  }

  // 배율 s로 놓는다. 화면에 들어가면 가운데에, 넘치면 왼쪽 위 끝에 맞춘다.
  function place(s) {
    var sw = stage.clientWidth;
    var sh = stage.clientHeight;
    view.s = clamp(s);
    var w = view.w * view.s;
    var h = view.h * view.s;
    view.x = w <= sw - 2 * MARGIN ? (sw - w) / 2 : MARGIN;
    view.y = h <= sh - 2 * MARGIN ? (sh - h) / 2 : MARGIN;
    apply();
  }

  // 그림 전체가 화면에 들어가는 배율
  function containScale() {
    return Math.min(
      (stage.clientWidth - 2 * MARGIN) / view.w,
      (stage.clientHeight - 2 * MARGIN) / view.h,
      view.maxFit
    );
  }

  function fit() {
    if (canvas) place(containScale());
  }

  // 처음 열 때는 화면에 맞추되 본문에서 보던 크기보다 작아지지는 않게 한다.
  // 세로로 긴 시퀀스 그림은 화면에 다 넣으면 오히려 작아지므로, 이때는 위에서부터 보여 준다.
  function initialView() {
    place(Math.max(containScale(), view.pageScale));
  }

  // (cx, cy)는 화면(stage) 좌표. 그 점이 제자리에 있도록 확대·축소한다.
  function zoomAt(cx, cy, factor) {
    if (!canvas) return;
    var s = clamp(view.s * factor);
    // 더 줄일 수 없는 크기에 닿으면 그림을 가운데로 모아 전체를 보여 준다.
    if (factor < 1 && s <= minScale() + 1e-6) {
      place(s);
      return;
    }
    var k = s / view.s;
    view.x = cx - (cx - view.x) * k;
    view.y = cy - (cy - view.y) * k;
    view.s = s;
    apply();
  }

  function zoomCenter(factor) {
    zoomAt(stage.clientWidth / 2, stage.clientHeight / 2, factor);
  }

  function point(e) {
    var r = stage.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function build() {
    dialog = document.createElement("dialog");
    dialog.className = "dv-dialog";
    dialog.setAttribute("aria-label", "그림 크게 보기");
    // 위쪽 막대: 왼쪽에 확대·축소 버튼과 사용법, 오른쪽 끝에 닫기 버튼. 그림 영역은 막대 아래부터다.
    dialog.innerHTML =
      '<div class="dv-topbar">' +
      '<div class="dv-controls">' +
      '<button type="button" data-dv="out" title="축소 (-)" aria-label="축소">&minus;</button>' +
      '<button type="button" data-dv="fit" class="dv-zoom" title="화면에 맞춤 (0)" aria-label="화면에 맞춤">100%</button>' +
      '<button type="button" data-dv="in" title="확대 (+)" aria-label="확대">+</button>' +
      "</div>" +
      '<div class="dv-hint">휠: 확대·축소 · 드래그: 이동 · 더블클릭: 화면에 맞춤 · Esc: 닫기</div>' +
      '<button type="button" data-dv="close" class="dv-close" title="닫기 (Esc)" aria-label="닫기">&times;</button>' +
      "</div>" +
      // 열 때 첫 버튼에 포커스 테두리가 생기지 않게 포커스를 그림 영역에 둔다. 키보드 조작은 그대로 된다.
      '<div class="dv-stage" tabindex="-1" autofocus></div>';
    document.body.appendChild(dialog);
    stage = dialog.querySelector(".dv-stage");
    zoomLabel = dialog.querySelector(".dv-zoom");

    dialog.querySelector(".dv-topbar").addEventListener("click", function (e) {
      var button = e.target.closest("button");
      if (!button) return;
      var action = button.getAttribute("data-dv");
      if (action === "in") zoomCenter(1.25);
      else if (action === "out") zoomCenter(0.8);
      else if (action === "fit") fit();
      else if (action === "close") dialog.close();
    });

    dialog.addEventListener("keydown", function (e) {
      if (e.key === "+" || e.key === "=") zoomCenter(1.25);
      else if (e.key === "-" || e.key === "_") zoomCenter(0.8);
      else if (e.key === "0") fit();
      else return;
      e.preventDefault();
    });

    dialog.addEventListener("close", function () {
      if (restore) {
        restore();
        restore = null;
      }
      if (canvas) {
        canvas.remove();
        canvas = null;
      }
      pointers.clear();
      stage.classList.remove("dv-dragging");
    });

    // 휠: 커서 위치를 중심으로 확대·축소. 터치패드 집기(ctrlKey)는 변화량이 작아서 더 크게 반영한다.
    stage.addEventListener(
      "wheel",
      function (e) {
        e.preventDefault();
        var unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
        var rate = e.ctrlKey ? 0.01 : 0.0015;
        var p = point(e);
        zoomAt(p.x, p.y, Math.exp(-e.deltaY * unit * rate));
      },
      { passive: false }
    );

    // 끌기(한 손가락·마우스)와 두 손가락 확대
    var pointers = new Map();
    var downPoint = null;
    var downOnCanvas = false;
    var moved = false;

    stage.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      e.preventDefault();
      stage.setPointerCapture(e.pointerId);
      if (pointers.size === 0) {
        downPoint = point(e);
        downOnCanvas = !!canvas && canvas.contains(e.target);
        moved = false;
      }
      pointers.set(e.pointerId, point(e));
      stage.classList.add("dv-dragging");
    });

    stage.addEventListener("pointermove", function (e) {
      if (!pointers.has(e.pointerId) || !canvas) return;
      var prev = pointers.get(e.pointerId);
      var cur = point(e);
      if (pointers.size === 1) {
        view.x += cur.x - prev.x;
        view.y += cur.y - prev.y;
        apply();
      } else if (pointers.size === 2) {
        var other = null;
        pointers.forEach(function (p, id) {
          if (id !== e.pointerId) other = p;
        });
        var d0 = Math.hypot(prev.x - other.x, prev.y - other.y);
        var d1 = Math.hypot(cur.x - other.x, cur.y - other.y);
        view.x += (cur.x - prev.x) / 2;
        view.y += (cur.y - prev.y) / 2;
        if (d0 > 0) zoomAt((cur.x + other.x) / 2, (cur.y + other.y) / 2, d1 / d0);
        else apply();
      }
      pointers.set(e.pointerId, cur);
      if (downPoint && Math.hypot(cur.x - downPoint.x, cur.y - downPoint.y) > MOVE_THRESHOLD) {
        moved = true;
      }
    });

    function release(e) {
      if (!pointers.has(e.pointerId)) return;
      pointers.delete(e.pointerId);
      if (pointers.size > 0) return;
      stage.classList.remove("dv-dragging");
      // 그림 바깥을 끌지 않고 누르면 닫는다.
      if (e.type === "pointerup" && !moved && !downOnCanvas) dialog.close();
    }
    stage.addEventListener("pointerup", release);
    stage.addEventListener("pointercancel", release);

    // 끌기 때문에 포인터를 붙잡고 있어서 dblclick의 target은 늘 stage다. 누른 곳은 pointerdown에서 기억한 값으로 판단한다.
    stage.addEventListener("dblclick", function () {
      if (downOnCanvas) fit();
    });
  }

  function newCanvas() {
    if (!dialog) build();
    canvas = document.createElement("div");
    canvas.className = "dv-canvas";
    stage.appendChild(canvas);
    return canvas;
  }

  // maxFit: 화면에 맞출 때 원래 크기의 몇 배까지 키울지. SVG는 키워도 선명하고, 사진은 원래 크기까지만.
  // pageScale: 본문에서 보이던 배율(원래 크기 대비). 처음 열 때 이보다 작게 보이지 않게 한다.
  function show(maxFit, pageScale) {
    dialog.showModal();
    view.w = canvas.offsetWidth;
    view.h = canvas.offsetHeight;
    view.maxFit = maxFit;
    view.pageScale = pageScale || 0;
    initialView();
  }

  function openMermaid(host) {
    var source = sources.get(host);
    var mermaid = window.mermaid;
    if (!source || !mermaid || typeof mermaid.render !== "function") {
      openHost(host);
      return;
    }
    var hostWidth = host.getBoundingClientRect().width;
    busy = true;
    Promise.resolve(mermaid.render("dv-mermaid-" + renderSeq++, source))
      .then(function (result) {
        var box = newCanvas();
        var root = box.attachShadow({ mode: "open" });
        root.innerHTML = result.svg;
        var svg = root.querySelector("svg");
        if (!svg) throw new Error("mermaid가 SVG를 돌려주지 않았다");
        // 본문에서는 width=100%, max-width=원래 폭이라 칸이 좁으면 줄어 보인다. 창에서는 원래 크기로 놓는다.
        var vb = svg.viewBox && svg.viewBox.baseVal;
        var pageScale = 1;
        if (vb && vb.width && vb.height) {
          svg.style.maxWidth = "none";
          svg.setAttribute("width", vb.width);
          svg.setAttribute("height", vb.height);
          pageScale = Math.min(1, hostWidth / vb.width);
        }
        svg.style.display = "block";
        show(2, pageScale);
      })
      .catch(function (err) {
        if (canvas) {
          canvas.remove();
          canvas = null;
        }
        if (window.console) console.warn("diagram-viewer: 다시 그리기 실패, 그림 상자를 옮겨 띄운다", err);
        openHost(host);
      })
      .then(function () {
        busy = false;
      });
  }

  // 그림 상자를 통째로 옮겨 띄운다. 본문에는 같은 높이의 빈 자리를 남겨 화면이 밀리지 않게 한다.
  function openHost(host) {
    var rect = host.getBoundingClientRect();
    var placeholder = document.createElement("div");
    placeholder.style.height = rect.height + "px";
    host.replaceWith(placeholder);
    var box = newCanvas();
    box.style.width = rect.width + "px";
    box.appendChild(host);
    restore = function () {
      placeholder.replaceWith(host);
    };
    show(2, 1);
  }

  function openImage(img) {
    var shownWidth = img.getBoundingClientRect().width;
    var copy = new Image();
    copy.alt = img.alt || "";
    copy.draggable = false;
    busy = true;
    copy.onload = function () {
      busy = false;
      var box = newCanvas();
      copy.width = copy.naturalWidth;
      copy.height = copy.naturalHeight;
      box.appendChild(copy);
      show(1, copy.naturalWidth ? shownWidth / copy.naturalWidth : 0);
    };
    copy.onerror = function () {
      busy = false;
    };
    copy.src = img.currentSrc || img.src;
  }

  function zoomableImage(img) {
    return (
      !img.closest("a") &&
      !img.classList.contains("twemoji") &&
      !img.classList.contains("emojione") &&
      !img.classList.contains("no-zoom")
    );
  }

  // 3. 본문에서 그림을 누르면 연다.
  document.addEventListener("click", function (e) {
    if (busy || e.defaultPrevented || e.button !== 0) return;
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    if (typeof HTMLDialogElement === "undefined") return;
    var target = e.target;
    if (!(target instanceof Element) || target.closest(".dv-dialog")) return;

    var host = target.closest(".md-typeset div.mermaid");
    if (host) {
      e.preventDefault();
      openMermaid(host);
      return;
    }
    var img = target.closest(".md-typeset img");
    if (img && zoomableImage(img)) {
      e.preventDefault();
      openImage(img);
    }
  });

  // 그림 위에 마우스를 올리면 누를 수 있다는 안내를 띄운다.
  document.addEventListener("mouseover", function (e) {
    var target = e.target;
    if (!(target instanceof Element)) return;
    var host = target.closest(".md-typeset div.mermaid");
    if (host && !host.hasAttribute("title")) host.setAttribute("title", "눌러서 크게 보기");
  });
})();
