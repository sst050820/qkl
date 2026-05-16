// 公益捐赠溯源平台 · 前端交互

document.addEventListener('DOMContentLoaded', function () {

  // ===== 照片预览 =====
  const photoInput = document.querySelector('input[type="file"][name="photo"]');
  const photoPreview = document.getElementById('photo-preview');
  if (photoInput && photoPreview) {
    photoInput.addEventListener('change', function () {
      const file = this.files[0];
      if (!file) { photoPreview.style.display = 'none'; return; }
      const reader = new FileReader();
      reader.onload = function (e) {
        photoPreview.src = e.target.result;
        photoPreview.style.display = 'block';
      };
      reader.readAsDataURL(file);
    });
  }

  // ===== 历史记录展开/折叠 =====
  document.querySelectorAll('.toggle-history').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const targetId = this.dataset.target;
      const row = document.getElementById(targetId);
      if (!row) return;
      const visible = row.classList.contains('visible');
      // 折叠其他展开行
      document.querySelectorAll('.hidden-row.visible').forEach(function (r) {
        if (r !== row) r.classList.remove('visible');
      });
      document.querySelectorAll('.toggle-history').forEach(function (b) {
        if (b !== btn) b.textContent = '查看历史';
      });
      row.classList.toggle('visible', !visible);
      this.textContent = visible ? '查看历史' : '收起历史';
    });
  });

  // ===== 机构注册：动态显示机构选择 =====
  const roleSelect = document.getElementById('role-select');
  if (roleSelect) {
    // 目前不再显示机构选择，仓库/快递站角色会自动关联默认节点。
  }

  // ===== Flash 消息自动淡出 =====
  document.querySelectorAll('.flash').forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity .5s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 520);
    }, 5000);
  });

});