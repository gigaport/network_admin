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

  function escHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function showForm(device) {
    $('#f_id').val(device ? device.id : '');
    $('#f_device_name').val(device ? device.device_name : '').prop('readonly', !!device);
    $('#f_ip').val(device ? device.ip : '');
    $('#f_os').val(device ? device.os : 'nxos');
    $('#f_client_vlan').val(device ? device.client_vlan : 1100);
    $('#f_join_products').val(device ? device.join_products : '');
    $('#f_groups').val(device ? device.groups : 'product');
    $('#f_description').val(device ? (device.description || '') : '');
    $('#f_enabled').prop('checked', device ? !!device.enabled : true);
    $form.show();
    $('#f_device_name').focus();
  }

  function hideForm() {
    $form.hide();
  }

  function renderRows(rows) {
    if (!rows || rows.length === 0) {
      $tbody.html('<tr><td colspan="9" class="text-center text-muted py-3">등록된 대상 장비가 없습니다.</td></tr>');
      return;
    }
    var html = '';
    rows.forEach(function (r, idx) {
      var row = escHtml(JSON.stringify(r));
      html += '<tr data-id="' + r.id + '">'
        + '<td>' + (idx + 1) + '</td>'
        + '<td><code>' + escHtml(r.device_name) + '</code></td>'
        + '<td>' + escHtml(r.ip) + '</td>'
        + '<td>' + escHtml(r.os) + '</td>'
        + '<td style="font-size:0.78rem; max-width:280px;" class="text-truncate" title="' + escHtml(r.join_products || '') + '">' + escHtml(r.join_products || '-') + '</td>'
        + '<td class="text-center">' + escHtml(r.client_vlan) + '</td>'
        + '<td>' + escHtml(r.groups || '-') + '</td>'
        + '<td class="text-center">'
        +   (r.enabled
              ? '<span class="badge bg-success-subtle text-success">ON</span>'
              : '<span class="badge bg-secondary-subtle text-secondary">OFF</span>')
        + '</td>'
        + '<td class="text-center">'
        +   '<button class="btn btn-sm btn-link p-0 me-2 btn-edit" title="수정"><i class="fas fa-edit"></i></button>'
        +   '<button class="btn btn-sm btn-link p-0 text-danger btn-del" title="삭제"><i class="fas fa-trash"></i></button>'
        + '</td>'
        + '</tr>'
        + '<tr style="display:none" data-raw="true"><td><script type="application/json">' + row + '</' + 'script></td></tr>';
    });
    $tbody.html(html);
  }

  function loadList() {
    $tbody.html('<tr><td colspan="9" class="text-center text-muted py-3">로딩 중...</td></tr>');
    $.ajax({
      url: '/pr_multicast_api/target_devices',
      method: 'GET',
      data: { market_type: MARKET_TYPE },
    }).done(function (resp) {
      if (resp && resp.success) {
        renderRows(resp.data || []);
      } else {
        $tbody.html('<tr><td colspan="9" class="text-center text-danger py-3">로드 실패: ' + escHtml((resp && resp.error) || 'unknown') + '</td></tr>');
      }
    }).fail(function (xhr) {
      $tbody.html('<tr><td colspan="9" class="text-center text-danger py-3">로드 실패 (HTTP ' + xhr.status + ')</td></tr>');
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

    $tbody.on('click', '.btn-edit', function () {
      var $tr = $(this).closest('tr');
      // 다음 hidden row 에서 JSON 추출
      var raw = $tr.next('[data-raw=true]').find('script').text();
      try { showForm(JSON.parse(raw)); } catch (e) { alert('수정 데이터 파싱 실패'); }
    });

    $tbody.on('click', '.btn-del', function () {
      var $tr = $(this).closest('tr');
      var id = $tr.data('id');
      var deviceName = $tr.find('code').text();
      deleteRow(id, deviceName);
    });

    // 모달 닫힐 때 폼 숨김
    $modal.on('hidden.bs.modal', hideForm);
  });
})();
