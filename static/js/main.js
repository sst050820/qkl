window.addEventListener('DOMContentLoaded', function () {
  const forms = document.querySelectorAll('form');
  forms.forEach((form) => {
    form.addEventListener('submit', function () {
      const submitButton = form.querySelector('input[type="submit"], button[type="submit"]');
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.value = '提交中...';
      }
    });
  });

  const photoInput = document.querySelector('input[type="file"][name="photo"]');
  const previewImage = document.getElementById('photo-preview');
  if (photoInput && previewImage) {
    photoInput.addEventListener('change', function (event) {
      const file = event.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = function (e) {
          previewImage.src = e.target.result;
          previewImage.style.display = 'block';
        };
        reader.readAsDataURL(file);
      } else {
        previewImage.style.display = 'none';
      }
    });
  }

  document.querySelectorAll('.toggle-history').forEach((button) => {
    button.addEventListener('click', function (event) {
      event.preventDefault();
      const targetId = this.dataset.target;
      const panel = document.getElementById(targetId);
      if (panel) {
        panel.classList.toggle('hidden-row');
      }
    });
  });
});
