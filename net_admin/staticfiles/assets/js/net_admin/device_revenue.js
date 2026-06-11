/* 장비 매출내역 페이지 */
(function () {
  let dataTable = null;

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

  function renderTable(rows) {
    if (dataTable) {
      dataTable.clear();
      dataTable.rows.add(rows.map(rowToArray));
      dataTable.draw(false);
      updateFooter(rows);
      updateStats(rows);
      return;
    }
    dataTable = new DataTable('#deviceRevenueTable', {
      data: rows.map(rowToArray),
      pageLength: 25,
      lengthMenu: [10, 25, 50, 100, 500],
      order: [[0, 'asc'], [1, 'asc'], [3, 'asc']],
      language: {
        emptyTable: '요금기준이 지정된 장비가 없습니다.',
        search: '검색:',
        info: '_TOTAL_건 중 _START_–_END_',
        infoEmpty: '0건',
        infoFiltered: '(전체 _MAX_건 중)',
        lengthMenu: '_MENU_건씩 보기',
        paginate: { first: '처음', previous: '이전', next: '다음', last: '마지막' },
      },
      columnDefs: [
        { targets: 9, className: 'text-end' },
      ],
    });
    updateFooter(rows);
    updateStats(rows);
  }

  function rowToArray(r) {
    return [
      escHtml(r.member_code) || '-',
      escHtml(r.datacenter_code || r.location_name) || '-',
      escHtml(r.address_summary) || '-',
      escHtml(r.device_name),
      escHtml(r.role) || '-',
      escHtml(r.manufacturer) || '-',
      escHtml(r.model) || '-',
      r.fee_code ? `<span class="badge bg-secondary-subtle text-secondary-emphasis">${escHtml(r.fee_code)}</span>` : '-',
      escHtml(r.fee_description) || '-',
      fmtNumber(r.fee_price),
    ];
  }

  function updateFooter(rows) {
    const total = rows.reduce((s, r) => s + (Number(r.fee_price) || 0), 0);
    document.getElementById('footerTotalPrice').textContent = fmtNumber(total);
  }

  function updateStats(rows) {
    const members = new Set(rows.map(r => r.member_code).filter(Boolean));
    const total = rows.reduce((s, r) => s + (Number(r.fee_price) || 0), 0);
    document.getElementById('stat_devices').textContent = fmtNumber(rows.length) + '대';
    document.getElementById('stat_members').textContent = fmtNumber(members.size) + '사';
    document.getElementById('stat_grand_total').textContent = fmtNumber(total) + '원';
  }

  function fetchAndRender() {
    fetch('/device_revenue/get_device_revenue')
      .then(r => r.json())
      .then(d => {
        if (!d.success) {
          alert('장비 매출내역 조회 실패: ' + (d.error || 'unknown'));
          return;
        }
        renderTable(d.data || []);
      })
      .catch(e => {
        console.error(e);
        alert('장비 매출내역 조회 오류: ' + e.message);
      });
  }

  window.refreshDeviceRevenue = fetchAndRender;
  document.addEventListener('DOMContentLoaded', fetchAndRender);
})();
