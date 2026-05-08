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
});
