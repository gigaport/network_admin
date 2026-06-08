/* 멀티캐스트 대상장비 관리 모달 (회원사-운영시세(API) 전용)
 *
 * 사용 위치: templates/pr_multicast_api.html
 * 의존: jQuery, Bootstrap 5 Modal
 */
(function () {
  'use strict';

  var MARKET_TYPE = 'pr_members_api';
  var $modal = null;
  var $tbody = null;
  var $form = null;

  // 현재 화면에 표시된 장비 list (클로저 보관) — id 로 안전하게 lookup
  var loadedDevices = [];

  function escHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function showForm(device) {
    if (device) {
      $('#formTitle').html('<i class="fas fa-pen me-1 text-success"></i>장비 수정 - <code>' + escHtml(device.device_name) + '</code>');
    } else {
      $('#formTitle').html('<i class="fas fa-plus me-1 text-success"></i>장비 추가');
    }
    $('#f_id').val(device ? device.id : '');
    $('#f_device_name').val(device ? device.device_name : '').prop('readonly', !!device);
    $('#f_ip').val(device ? device.ip : '');
    $('#f_os').val(device ? device.os : 'nxos');
    $('#f_client_vlan').val(device ? device.client_vlan : 1100);
    $('#f_join_products').val(device ? device.join_products : '');
    $('#f_groups').val(device ? device.groups : 'product');
    $('#f_description').val(device ? (device.description || '') : '');
    $('#f_enabled').prop('checked', device ? !!device.enabled : true);
    $form.slideDown(150);
    setTimeout(function () { $('#f_device_name').focus(); }, 160);
  }

  function hideForm() {
    $form.slideUp(150);
  }

  function renderRows(rows) {
    loadedDevices = rows || [];
    var count = loadedDevices.length;
    $('#mctdRowCount').text(count > 0 ? '총 ' + count + ' 대' : '');

    if (count === 0) {
      $tbody.html(
        '<tr><td colspan="9" class="empty-state">' +
          '<i class="fas fa-box-open"></i>' +
          '등록된 대상 장비가 없습니다.<br>' +
          '<small>우측 상단의 <b>장비 추가</b> 버튼으로 새 장비를 등록하세요.</small>' +
        '</td></tr>'
      );
      return;
    }

    var html = '';
    loadedDevices.forEach(function (r, idx) {
      html += '<tr data-id="' + r.id + '">'
        + '<td style="color:#9ca3af;">' + (idx + 1) + '</td>'
        + '<td><code>' + escHtml(r.device_name) + '</code></td>'
        + '<td><span style="font-family:ui-monospace,monospace; color:#475569;">' + escHtml(r.ip) + '</span></td>'
        + '<td><span class="badge bg-secondary-subtle text-secondary" style="font-size:0.7rem;">' + escHtml(r.os) + '</span></td>'
        + '<td style="font-size:0.78rem; max-width:280px;" class="text-truncate" title="' + escHtml(r.join_products || '') + '">' + escHtml(r.join_products || '-') + '</td>'
        + '<td class="text-center"><span style="font-weight:600; color:' + (parseInt(r.client_vlan,10) !== 1100 ? '#ef4444' : '#475569') + ';">' + escHtml(r.client_vlan) + '</span></td>'
        + '<td><small style="color:#6b7280;">' + escHtml(r.groups || '-') + '</small></td>'
        + '<td class="text-center">'
        +   (r.enabled
              ? '<span class="badge-on">ON</span>'
              : '<span class="badge-off">OFF</span>')
        + '</td>'
        + '<td class="text-center">'
        +   '<button class="row-action-btn btn-edit" title="수정"><i class="fas fa-pen"></i></button>'
        +   '<button class="row-action-btn btn-del" title="삭제"><i class="fas fa-trash"></i></button>'
        + '</td>'
        + '</tr>';
    });
    $tbody.html(html);
  }

  function loadList() {
    $tbody.html('<tr><td colspan="9" class="empty-state"><i class="fas fa-spinner fa-spin"></i>로딩 중...</td></tr>');
    $.ajax({
      url: '/pr_multicast_api/target_devices',
      method: 'GET',
      data: { market_type: MARKET_TYPE },
    }).done(function (resp) {
      if (resp && resp.success) {
        renderRows(resp.data || []);
      } else {
        $tbody.html('<tr><td colspan="9" class="empty-state text-danger">로드 실패: ' + escHtml((resp && resp.error) || 'unknown') + '</td></tr>');
      }
    }).fail(function (xhr) {
      $tbody.html('<tr><td colspan="9" class="empty-state text-danger">로드 실패 (HTTP ' + xhr.status + ')</td></tr>');
    });
  }

  function getFormPayload() {
    return {
      market_type: MARKET_TYPE,
      device_name: $('#f_device_name').val().trim(),
      ip: $('#f_ip').val().trim(),
      os: $('#f_os').val(),
      join_products: $('#f_join_products').val().trim(),
      client_vlan: parseInt($('#f_client_vlan').val() || '1100', 10),
      groups: $('#f_groups').val().trim(),
      description: $('#f_description').val().trim(),
      enabled: $('#f_enabled').is(':checked'),
    };
  }

  function saveForm() {
    var id = $('#f_id').val();
    var payload = getFormPayload();

    if (!payload.device_name) { alert('장비명을 입력하세요.'); return; }
    if (!payload.ip) { alert('IP 를 입력하세요.'); return; }

    var url = id
      ? '/pr_multicast_api/target_devices/' + id + '/update'
      : '/pr_multicast_api/target_devices/create';

    $.ajax({
      url: url, method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(payload),
    }).done(function (resp) {
      if (resp && (resp.success || resp.id)) {
        hideForm();
        loadList();
      } else {
        alert('저장 실패: ' + ((resp && (resp.detail || resp.error)) || 'unknown'));
      }
    }).fail(function (xhr) {
      var msg = 'HTTP ' + xhr.status;
      try {
        var j = JSON.parse(xhr.responseText);
        if (j && (j.detail || j.error)) msg += ' - ' + (j.detail || j.error);
      } catch (e) {}
      alert('저장 실패: ' + msg);
    });
  }

  function deleteRow(id, deviceName) {
    if (!confirm('장비 [' + deviceName + '] 을(를) 삭제하시겠습니까?')) return;
    $.ajax({
      url: '/pr_multicast_api/target_devices/' + id + '/delete',
      method: 'POST',
    }).done(function (resp) {
      if (resp && resp.success) {
        loadList();
      } else {
        alert('삭제 실패: ' + ((resp && (resp.detail || resp.error)) || 'unknown'));
      }
    }).fail(function (xhr) {
      alert('삭제 실패 (HTTP ' + xhr.status + ')');
    });
  }

  $(function () {
    $modal = $('#targetDevicesModal');
    if (!$modal.length) return;

    $tbody = $('#targetDevicesTbody');
    $form = $('#deviceFormBox');

    $modal.on('shown.bs.modal', loadList);

    $('#btnAddDevice').on('click', function () { showForm(null); });
    $('#btnCancelForm').on('click', hideForm);
    $('#btnSaveForm').on('click', saveForm);

    // 수정: 클로저의 loadedDevices 에서 id 로 찾음 (안전)
    $tbody.on('click', '.btn-edit', function () {
      var id = parseInt($(this).closest('tr').data('id'), 10);
      var dev = loadedDevices.find(function (d) { return d.id === id; });
      if (dev) {
        showForm(dev);
      } else {
        alert('수정할 장비를 찾을 수 없습니다 (id=' + id + ')');
      }
    });

    $tbody.on('click', '.btn-del', function () {
      var id = parseInt($(this).closest('tr').data('id'), 10);
      var dev = loadedDevices.find(function (d) { return d.id === id; });
      deleteRow(id, dev ? dev.device_name : '?');
    });

    // 모달 닫힐 때 폼 숨김
    $modal.on('hidden.bs.modal', function () { $form.hide(); });
  });
})();
