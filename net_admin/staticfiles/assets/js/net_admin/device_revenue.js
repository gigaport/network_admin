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

    let swCnt = 0, swRev = 0, fwCnt = 0, fwRev = 0;
    const dcRev = {};   // 데이터센터별 매출
    rows.forEach(r => {
      const price = Number(r.fee_price) || 0;
      if (r.device_kind === '스위치') { swCnt++; swRev += price; }
      else if (r.device_kind === '방화벽') { fwCnt++; fwRev += price; }
      const dc = r.datacenter_code || '미지정';
      if (!dcRev[dc]) dcRev[dc] = { cnt: 0, rev: 0 };
      dcRev[dc].cnt++;
      dcRev[dc].rev += price;
    });

    document.getElementById('stat_devices').textContent = fmtNumber(rows.length) + '대';
    document.getElementById('stat_members').textContent = fmtNumber(members.size) + '사';
    document.getElementById('stat_grand_total').textContent = fmtNumber(total) + '원';
    document.getElementById('stat_switch_cnt').textContent = fmtNumber(swCnt) + '대';
    document.getElementById('stat_switch_rev').textContent = fmtNumber(swRev) + '원';
    document.getElementById('stat_fw_cnt').textContent = fmtNumber(fwCnt) + '대';
    document.getElementById('stat_fw_rev').textContent = fmtNumber(fwRev) + '원';

    // 데이터센터별 매출 칩 렌더링 (매출 큰 순)
    const dcBox = document.getElementById('summaryByDc');
    if (dcBox) {
      const entries = Object.keys(dcRev).map(k => [k, dcRev[k]]).sort((a, b) => b[1].rev - a[1].rev);
      dcBox.innerHTML = entries.map(function (e) {
        const code = e[0], v = e[1];
        return '<span class="badge badge-phoenix ' + dcBadgeClass(code) + '" ' +
          'style="font-size:0.8rem; padding:6px 10px; font-weight:600;">' +
          escHtml(code) + ' · ' + fmtNumber(v.cnt) + '대 · ' + fmtNumber(v.rev) + '원</span>';
      }).join('');
    }
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
      orderCellsTop: true,
      order: [[1, 'asc'], [3, 'asc'], [6, 'asc']],
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
        { data: 'member_number' },
        { data: 'company_name' },
        { data: 'datacenter_code' },
        { data: 'address_summary' },
        { data: 'device_kind' },
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
          width: '5%',
          className: 'text-center py-2 align-middle',
          render: function (data, type) {
            // 정렬/타입 판정 시에는 숫자값 사용 (null 은 맨 앞으로)
            if (type === 'sort' || type === 'type') {
              return (data === null || data === undefined || data === '') ? -1 : Number(data);
            }
            if (data === null || data === undefined || data === '') return '-';
            return escHtml(String(data));
          },
        },
        {
          targets: 2,
          width: '11%',
          className: 'text-start py-2 align-middle fw-semibold',
          render: function (data) {
            if (!data) return '-';
            return '<span title="' + escHtml(data) + '">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 3,
          width: '6%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            return '<span class="badge badge-phoenix ' + dcBadgeClass(data) + '">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 4,
          width: '13%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            return '<span title="' + escHtml(data) + '">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 5,
          width: '6%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            var cls = data === '스위치' ? 'badge-phoenix-info' : (data === '방화벽' ? 'badge-phoenix-danger' : 'badge-phoenix-secondary');
            return '<span class="badge badge-phoenix ' + cls + '">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 6,
          width: '12%',
          className: 'text-center py-2 align-middle fw-semibold',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 7,
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
          targets: 8,
          width: '6%',
          className: 'text-center py-2 align-middle',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 9,
          width: '8%',
          className: 'text-center py-2 align-middle fw-semibold',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 10,
          width: '8%',
          className: 'text-center py-2 align-middle',
          render: function (data) {
            if (!data) return '-';
            return '<span class="badge badge-phoenix badge-phoenix-secondary">' + escHtml(data) + '</span>';
          },
        },
        {
          targets: 11,
          width: '13%',
          className: 'text-center py-2 align-middle',
          render: function (data) { return escHtml(data) || '-'; },
        },
        {
          targets: 12,
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

    // 헤더 바로 아래에 검색 행(두 번째 thead row) 추가
    var $filterRow = $('<tr class="filter-row"></tr>');
    deviceRevenueTable.columns().every(function () {
      var title = $(this.header()).text();
      var $th = $('<th style="padding:4px 6px; background:#fff;"></th>');
      $th.append(
        '<input type="text" class="form-control form-control-sm" placeholder="' +
          title +
          ' 검색" style="font-size:0.65rem; padding:2px 4px; font-weight:400;" />'
      );
      $filterRow.append($th);
    });
    $('#deviceRevenueTable thead').append($filterRow);

    // 개별 열 검색 기능 적용 (검색 행 입력칸 ↔ 컬럼 매핑)
    deviceRevenueTable.columns().every(function (idx) {
      var that = this;
      $('input', $filterRow.find('th').eq(idx)).on('keyup change', function () {
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
    $('#deviceRevenueTable thead .filter-row input').val('');
    if (deviceRevenueTable) {
      deviceRevenueTable.search('').columns().search('').draw();
    }
  };

  $(document).ready(function () {
    initTable();
  });
})();
