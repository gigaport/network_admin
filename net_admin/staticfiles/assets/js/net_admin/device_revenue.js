/* 장비 매출내역 페이지 — info_company_circuits 스타일 */
(function () {
  let deviceRevenueTable = null;

  function fmtNumber(n) {
    if (n === null || n === undefined || n === '') return '-';
    const v = Number(n);
    if (Number.isNaN(v)) return '-';
    return v.toLocaleString('ko-KR');
  }

  function escHtml(v) {
    if (v === null || v === undefined) return '';
    return String(v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function updateSummary(rows) {
    const members = new Set(rows.map(r => r.member_code).filter(Boolean));
    const total = rows.reduce((s, r) => s + (Number(r.fee_price) || 0), 0);
    document.getElementById('stat_devices').textContent = fmtNumber(rows.length) + '대';
    document.getElementById('stat_members').textContent = fmtNumber(members.size) + '사';
    document.getElementById('stat_grand_total').textContent = fmtNumber(total) + '원';
  }

  function dcBadgeClass(code) {
    switch (code) {
      case 'DC1': return 'badge-phoenix-primary';
      case 'DC2': return 'badge-phoenix-info';
      case 'DC3': return 'badge-phoenix-success';
      case 'DR': return 'badge-phoenix-warning';
      case 'PB_DR': return 'badge-phoenix-danger';
      case 'PB_메인': return 'badge-phoenix-info';
      default: return 'badge-phoenix-secondary';
    }
  }

  function initTable() {
    deviceRevenueTable = $('#deviceRevenueTable').DataTable({
      responsive: true,
      paging: false,
      searching: true,
      ordering: true,
      order: [[0, 'asc'], [1, 'asc'], [3, 'asc']],
      scrollX: true,
      scrollY: '60vh',
      scrollCollapse: true,
      language: {
        search: '검색:',
        info: '전체 _TOTAL_건',
        infoEmpty: '데이터가 없습니다',
        infoFiltered: '(전체 _MAX_건 중 필터링됨)',
        emptyTable: '요금기준이 지정된 장비가 없습니다.',
        zeroRecords: '검색 결과가 없습니다',
        loadingRecords: ' ',
      },
      dom:
        '<"row align-items-center"<"col-sm-12 col-md-6"><"col-sm-12 col-md-6 d-flex justify-content-end align-items-center gap-2"fB>>' +
        '<"row"<"col-sm-12"tr>>' +
        '<"row"<"col-sm-12"i>>',
      buttons: [
        {
          extend: 'excel',
          text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
          className: 'btn btn-success btn-sm',
          title: '장비_매출내역_' + new Date().toISOString().slice(0, 10),
          exportOptions: { columns: ':visible' },
        },
        {
          extend: 'csv',
          text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
          className: 'btn btn-info btn-sm',
          title: '장비_매출내역_' + new Date().toISOString().slice(0, 10),
          exportOptions: { columns: ':visible' },
        },
        {
          extend: 'copy',
          text: '<i class="fa-solid fa-copy me-2"></i>복사',
          className: 'btn btn-secondary btn-sm',
          exportOptions: { columns: ':visible' },
        },
      ],
      ajax: {
        url: '/device_revenue/get_device_revenue',
        type: 'GET',
        dataSrc: function (json) {
          if (json.success) {
            updateSummary(json.data || []);
            return json.data || [];
          }
          alert('데이터 로드 실패: ' + (json.error || 'unknown'));
          return [];
        },
        error: function (xhr, error, thrown) {
          console.error('AJAX Error:', error, thrown);
          alert('데이터 로드 중 오류가 발생했습니다.');
        },
      },
      columns: [
        { data: 'member_code' },
        { data: 'datacenter_code' },
        { data: 'address_summary' },
        { data: 'device_name' },
        { data: 'role' },
        { data: 'manufacturer' },
        { data: 'model' },
        { data: 'fee_code' },
        { data: 'fee_description' },
        { data: 'fee_price' },
      ],
      columnDefs: [
        {
          targets: 0,
          width: '5%',
          className: 'text-center py-2 align-middle fw-semibold',
          render: function (data) {
            if (!data) return '-';
            return '<span class="badge badge-phoenix badge-phoenix-primary">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 1,
          width: '6%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            return '<span class="badge badge-phoenix ' + dcBadgeClass(data) + '">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 2,
          width: '14%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            return '<span title="' + escHtml(data) + '">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 3,
          width: '15%',
          className: 'text-center py-2 align-middle fw-semibold',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 4,
          width: '5%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            var cls = 'badge-phoenix-secondary';
            if (data === 'PRD') cls = 'badge-phoenix-success';
            else if (data === 'DR') cls = 'badge-phoenix-warning';
            else if (data === 'TST') cls = 'badge-phoenix-info';
            else if (data === 'IDLE') cls = 'badge-phoenix-secondary';
            return '<span class="badge badge-phoenix ' + cls + '">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 5,
          width: '6%',
          className: 'text-center py-2 align-middle',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 6,
          width: '8%',
          className: 'text-center py-2 align-middle fw-semibold',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 7,
          width: '8%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            return '<span class="badge badge-phoenix badge-phoenix-secondary">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 8,
          width: '15%',
          className: 'text-center py-2 align-middle',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 9,
          width: '7%',
          className: 'text-end py-2 align-middle fw-semibold',
          render: function (data) {
            if (data === null || data === undefined) return '-';
            return fmtNumber(data);
          },
        },
      ],
      initComplete: function () {
        var overlay = document.getElementById('pageLoadingOverlay');
        if (overlay) {
          overlay.style.opacity = '0';
          setTimeout(function () { overlay.remove(); }, 400);
        }
      },
    });

    // tfoot 의 각 열에 검색 입력 필드 추가
    $('#deviceRevenueTable tfoot th').each(function () {
      var title = $(this).text();
      $(this).css({ 'font-size': '0.7rem', 'white-space': 'nowrap' });
      $(this).html(
        '<input type="text" class="form-control form-control-sm" placeholder="' +
          title +
          ' 검색" style="font-size:0.65rem; padding:2px 4px;" />'
      );
    });

    // 개별 열 검색 기능 적용
    deviceRevenueTable.columns().every(function () {
      var that = this;
      $('input', this.footer()).on('keyup change', function () {
        if (that.search() !== this.value) {
          that.search(this.value).draw();
        }
      });
    });
  }

  window.refreshDeviceRevenue = function () {
    if (deviceRevenueTable) {
      deviceRevenueTable.ajax.reload(null, false);
    } else {
      initTable();
    }
  };

  window.resetFilters = function () {
    $('#deviceRevenueTable tfoot input').val('');
    if (deviceRevenueTable) {
      deviceRevenueTable.search('').columns().search('').draw();
    }
  };

  $(document).ready(function () {
    initTable();
  });
})();
