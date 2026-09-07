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
