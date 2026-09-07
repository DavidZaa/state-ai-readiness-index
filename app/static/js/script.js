// The weight sliders.
//
// The form submits to the server rather than recomputing in the browser: the
// ranking a reader arrives at should be in a URL they can send to someone
// else, which is the whole point of letting them move the weights.

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-weights]");

  if (!form) return;

  form.querySelectorAll('input[type="range"]').forEach((slider) => {
    const output = form.querySelector(`output[for="${slider.id}"]`);

    const show = () => {
      if (output) output.textContent = Number(slider.value).toFixed(2);
    };

    show();
    slider.addEventListener("input", show);
  });
});

// The permalink. Weights already live in the query string, so "share" is just
// handing over the current URL — but nothing on the page said so, and a
// feature nobody can see is a feature nobody uses.
document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector("[data-permalink]");

  if (!button) return;

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      button.textContent = "Link copied";
    } catch {
      // Clipboard access is refused in plenty of ordinary situations, and the
      // URL is in the address bar either way.
      button.textContent = "Copy from the address bar";
    }

    setTimeout(() => {
      button.textContent = "Copy link to this ranking";
    }, 2500);
  });
});

// The state lookup posts to /state/<code>, which reads better in the address
// bar and gives each state a page worth linking to.
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-state-lookup]");

  if (!form) return;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const code = form.querySelector("select").value;
    window.location.href = `/state/${code}`;
  });
});

// State search. A datalist gives native autocomplete, so the input accepts a
// full name, a partial one, or a two-letter code without a combobox library.
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-state-search]");

  if (!form) return;

  const input = form.querySelector("input");
  const error = form.querySelector("[data-search-error]");
  const options = [...document.querySelectorAll("#state-names option")].map((option) => ({
    code: option.dataset.code,
    name: option.value,
  }));

  function resolve(text) {
    const query = text.trim().toLowerCase();

    if (!query) return null;

    return (
      options.find((o) => o.name.toLowerCase() === query) ||
      options.find((o) => o.code.toLowerCase() === query) ||
      options.find((o) => o.name.toLowerCase().startsWith(query)) ||
      null
    );
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    const match = resolve(input.value);

    if (!match) {
      error.hidden = false;
      error.textContent = `No state matches “${input.value.trim()}”.`;
      return;
    }

    error.hidden = true;
    window.location.href = `/state/${match.code}`;
  });

  input.addEventListener("input", () => {
    error.hidden = true;
  });
});

// The analysis. Progress reflects work actually happening on the server — the
// stream sends a step every fifty rankings — so the wait is the computation,
// not a timer pretending to be one.
document.addEventListener("DOMContentLoaded", () => {
  const panel = document.querySelector("[data-analysis]");

  if (!panel) return;

  const code = panel.dataset.code;
  const progress = panel.querySelector("[data-progress]");
  const fill = panel.querySelector("[data-progress-fill]");
  const label = panel.querySelector("[data-progress-label]");
  const result = panel.querySelector("[data-result]");

  const source = new EventSource(`/analyse/${code}/stream?trials=2000`);

  source.addEventListener("step", (event) => {
    const step = JSON.parse(event.data);
    const pct = step.total ? (step.done / step.total) * 100 : 0;

    fill.style.width = `${pct}%`;
    label.textContent = step.label;
  });

  source.addEventListener("result", (event) => {
    source.close();
    render(JSON.parse(event.data));
  });

  source.addEventListener("failed", () => {
    source.close();
    label.textContent = "Could not run the analysis.";
  });

  function render(data) {
    progress.hidden = true;
    result.hidden = false;

    panel.querySelector("[data-median]").textContent = `#${data.median}`;
    panel.querySelector("[data-trials]").textContent = data.trials.toLocaleString();

    const spread = data.p90 - data.p10;
    const reading =
      spread <= 3
        ? `This position barely moves. Across ${data.trials.toLocaleString()} differently weighted indexes it stayed between #${data.p10} and #${data.p90} four times out of five — the ranking is telling you about the state, not about the recipe.`
        : spread <= 12
          ? `This position is moderately sensitive to the weights: four times out of five it fell between #${data.p10} and #${data.p90}, and across every run it ranged from #${data.best} to #${data.worst}.`
          : `This position depends heavily on the weights. Four times in five it landed between #${data.p10} and #${data.p90}, and over every run it ranged from #${data.best} to #${data.worst} — a rank this movable says more about the index than the state.`;

    panel.querySelector("[data-reading]").textContent = reading;
    drawHistogram(data);
  }

  function drawHistogram(data) {
    const host = panel.querySelector("[data-histogram]");
    const counts = data.counts || {};
    const peak = Math.max(1, ...Object.values(counts));

    host.innerHTML = "";

    for (let rank = 1; rank <= 50; rank += 1) {
      const count = counts[rank] || 0;
      const bar = document.createElement("span");

      bar.className = "histogram__bar";
      bar.style.height = `${(count / peak) * 100}%`;
      bar.title = `Rank ${rank}: ${count} of ${data.trials}`;

      if (rank >= data.p10 && rank <= data.p90) bar.dataset.band = "true";
      if (rank === data.median) bar.dataset.median = "true";

      host.appendChild(bar);
    }
  }
});
