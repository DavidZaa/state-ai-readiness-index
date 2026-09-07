// First-visit explanation.
//
// A reader landing here sees a ranking and some charts with no idea why any of
// it is unusual. This says what the site is for in three sentences, then offers
// to point at the parts — offers, rather than starting, because a walkthrough
// that begins on its own assumes an interest nobody agreed to yet.
//
// Two things learned the hard way and worth keeping:
//
//  * Steps are resolved after the page has painted. Reading the DOM too early
//    finds nothing and silently drops half the tour.
//  * The tooltip is measured, not assumed. A step scrolled to the middle of the
//    screen has little room above it, and guessing the height puts the heading
//    off the top of the window.

(function () {
  "use strict";

  var WELCOME_KEY = "sari/welcomed/v1";
  var TOUR_KEY = "sari/tour-seen/v1";

  var STEPS = [
    {
      target: ".finding",
      title: "This number is the point",
      body: "It says how far the typical state moves when you change how much each measure counts. Nothing about the states changes — only the recipe.",
    },
    {
      target: ".ranges",
      title: "Every state has a range, not a rank",
      body: "Each line shows where a state usually landed across a thousand rankings. A long line means its position is not settled.",
    },
    {
      target: ".strips",
      title: "We check our own claim here",
      body: "States are grouped by whether they publish AI guidance. The rows sit on top of each other, so guidance does not come with better scores.",
    },
    {
      target: "[data-state-search]",
      title: "Look up any state",
      body: "Type a name and watch it get analysed — a thousand rankings built while you wait, then every position that state landed on.",
    },
    {
      target: ".masthead__nav",
      title: "Build your own ranking",
      body: "Explore lets you move the weights yourself. Method explains the two choices behind any ranking, and Sources lists every number and where it came from.",
    },
  ];

  // Storage that cannot be read counts as already seen. Getting this backwards
  // would interrupt every single visit for anyone with site data blocked.
  function store() {
    try {
      return window.localStorage || null;
    } catch (error) {
      return null;
    }
  }

  function seen(key) {
    var storage = store();

    if (!storage) return true;

    try {
      return storage.getItem(key) === "1";
    } catch (error) {
      return true;
    }
  }

  function remember(key) {
    var storage = store();

    if (!storage) return;

    try {
      storage.setItem(key, "1");
    } catch (error) {
      /* Nothing to do; the reader simply sees it again next time. */
    }
  }

  function forget(key) {
    var storage = store();

    try {
      if (storage) storage.removeItem(key);
    } catch (error) {
      /* ignore */
    }
  }

  /* ------------------------------------------------------------ the tour */

  function startTour() {
    var steps = STEPS.filter(function (step) {
      return document.querySelector(step.target);
    });

    if (!steps.length) return;

    var index = 0;

    var root = document.createElement("div");
    root.className = "tour";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-label", "Guided tour");

    var spot = document.createElement("div");
    spot.className = "tour__spot";

    var card = document.createElement("div");
    card.className = "tour__card";

    root.appendChild(spot);
    root.appendChild(card);
    document.body.appendChild(root);

    function finish() {
      remember(TOUR_KEY);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place);
      document.removeEventListener("keydown", onKey);
      root.remove();
    }

    function onKey(event) {
      if (event.key === "Escape") finish();
      else if (event.key === "ArrowRight") go(index + 1);
      else if (event.key === "ArrowLeft") go(index - 1);
    }

    function place() {
      var step = steps[index];
      var element = document.querySelector(step.target);

      if (!element) return;

      var rect = element.getBoundingClientRect();
      var pad = 8;
      var top = rect.top + window.scrollY - pad;
      var left = rect.left + window.scrollX - pad;

      spot.style.top = top + "px";
      spot.style.left = left + "px";
      spot.style.width = rect.width + pad * 2 + "px";
      spot.style.height = rect.height + pad * 2 + "px";

      // Measured, not assumed — see the note at the top of this file.
      var height = card.offsetHeight || 200;
      var width = card.offsetWidth || 320;
      var gap = 14;
      var viewTop = window.scrollY;
      var viewBottom = viewTop + window.innerHeight;

      var below = top + rect.height + pad * 2 + gap;
      var above = top - gap - height;
      var y = below;

      if (below + height > viewBottom - gap) {
        y = above >= viewTop + gap ? above : below;
      }

      card.style.top = Math.max(viewTop + gap, Math.min(y, viewBottom - height - gap)) + "px";
      card.style.left =
        Math.min(
          Math.max(left, window.scrollX + gap),
          window.scrollX + window.innerWidth - width - gap
        ) + "px";
    }

    function go(next) {
      if (next < 0 || next >= steps.length) return;

      index = next;
      render();
    }

    function render() {
      var step = steps[index];
      var last = index === steps.length - 1;

      card.innerHTML = "";

      var count = document.createElement("p");
      count.className = "tour__count";
      count.textContent = index + 1 + " of " + steps.length;

      var title = document.createElement("h2");
      title.className = "tour__title";
      title.textContent = step.title;

      var body = document.createElement("p");
      body.className = "tour__body";
      body.textContent = step.body;

      var actions = document.createElement("div");
      actions.className = "tour__actions";

      var next = document.createElement("button");
      next.type = "button";
      next.className = "button--primary";
      next.textContent = last ? "Done" : "Next";
      next.addEventListener("click", function () {
        if (last) finish();
        else go(index + 1);
      });
      actions.appendChild(next);

      if (index > 0) {
        var back = document.createElement("button");
        back.type = "button";
        back.className = "tour__back";
        back.textContent = "Back";
        back.addEventListener("click", function () {
          go(index - 1);
        });
        actions.appendChild(back);
      }

      if (!last) {
        var skip = document.createElement("button");
        skip.type = "button";
        skip.className = "tour__skip";
        skip.textContent = "Skip";
        skip.addEventListener("click", finish);
        actions.appendChild(skip);
      }

      card.appendChild(count);
      card.appendChild(title);
      card.appendChild(body);
      card.appendChild(actions);

      var element = document.querySelector(step.target);

      if (element) {
        element.scrollIntoView({
          block: "center",
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto"
            : "smooth",
        });
      }

      // Smooth scrolling keeps moving after this runs, so keep re-measuring
      // briefly rather than drawing the highlight where the target used to be.
      place();

      var ticker = setInterval(place, 100);
      setTimeout(function () {
        clearInterval(ticker);
      }, 700);
    }

    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, { passive: true });
    document.addEventListener("keydown", onKey);

    render();
  }

  /* --------------------------------------------------------- the welcome */

  function openWelcome() {
    var dialog = document.getElementById("welcome");

    if (!dialog) return;

    dialog.showModal();

    dialog.addEventListener("cancel", function (event) {
      event.preventDefault();
      close(false);
    });

    dialog.querySelector("[data-welcome-tour]").addEventListener("click", function () {
      close(true);
    });

    dialog.querySelector("[data-welcome-dismiss]").addEventListener("click", function () {
      close(false);
    });

    function close(withTour) {
      remember(WELCOME_KEY);
      dialog.close();

      if (withTour) {
        // A frame, so the dialog has finished closing and the page underneath
        // is laid out before anything measures it.
        requestAnimationFrame(startTour);
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // ?tour=1 starts it directly, so the walkthrough can be linked to — useful
    // for a demo, and the only way to see it again without clearing storage.
    if (/[?&]tour=1(&|$)/.test(window.location.search)) {
      requestAnimationFrame(startTour);
      return;
    }

    if (document.getElementById("welcome") && !seen(WELCOME_KEY)) {
      openWelcome();
    }

    var replay = document.querySelector("[data-replay-tour]");

    if (replay) {
      replay.addEventListener("click", function () {
        forget(TOUR_KEY);
        startTour();
      });
    }
  });
})();
