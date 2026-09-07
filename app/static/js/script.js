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
