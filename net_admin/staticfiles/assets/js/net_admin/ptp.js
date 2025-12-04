// static/assets/js/net_admin/ptp.js

$(document).ready(function () {
  const data_back = document.getElementById("back_data");
  const currentPath = data_back ? data_back.dataset.submenu : "";

  const $detailBody = $("#ptp-detail-body");
  const $detailModal = $("#modal_ptp_detail");
  const $detailTitle = $("#modal_ptp_detail_label");

  // =========================
  // 1. PTP 요약 DataTable 초기화
  // =========================
  const table = $('#ptp_summary_table').DataTable({
    responsive: true,
    paging: true,
    searching: true,
    ordering: true,
    pageLength: 50,
    lengthChange: false,
    ajax: {
      url: '/information/init',
      type: 'GET',
      data: {
        sub_menu: currentPath   // ARP와 동일한 방식
      }
      // 서버에서 반환 형식 예시:
      // {
      //   "data": [
      //     {
      //       "hostname": "PYD-PTP-L2-01",
      //       "offset": -98,
      //       "delay": 118.5,
      //       "jitter": 1.2,
      //       "packet_continuity": 100.0,
      //       "details": [
      //         {
      //           "interface": "Po1",
      //           "time": "04:55:07.115 UTC Nov 28 2025",
      //           "offset": -98,
      //           "delay": 119,
      //           "jitter": 0.999990387,
      //           "seq_id": 12473
      //         }
      //       ]
      //     },
      //     ...
      //   ]
      // }
    },
    columns: [
      { data: 'hostname' },           // 0 장비
      { data: 'offset' },             // 1 최신 시간 오차(ns)
      { data: 'delay' },              // 2 링크 지연(ns)
      { data: 'jitter' },             // 3 지터(ns)
      { data: 'packet_continuity' },  // 4 패킷 연속성(%)
      { data: null }                  // 5 상세보기 버튼
    ],
    columnDefs: [
      {
        targets: 0,
        width: '15%',
        createdCell: function (td) {
          $(td).addClass('text-center py-2 align-middle fw-bold');
        },
        render: function (data) {
          return data || '-';
        }
      },
      {
        targets: 1,
        width: '15%',
        createdCell: function (td) {
          $(td).addClass('text-center py-2 align-middle');
        },
        render: function (data) {
          return (data !== undefined && data !== null) ? data : '-';
        }
      },
      {
        targets: 2,
        width: '15%',
        createdCell: function (td) {
          $(td).addClass('text-center py-2 align-middle');
        },
        render: function (data) {
          return (data !== undefined && data !== null) ? data : '-';
        }
      },
      {
        targets: 3,
        width: '15%',
        createdCell: function (td) {
          $(td).addClass('text-center py-2 align-middle');
        },
        render: function (data) {
          return (data !== undefined && data !== null) ? data : '-';
        }
      },
      {
        targets: 4,
        width: '25%',
        createdCell: function (td) {
          $(td).addClass('text-center py-2 align-middle fw-bold');
        },
        render: function (data) {
          if (data === undefined || data === null || data === '-') return '-';
          return '<span class="text-primary">' + data + '%</span>';
        }
      },
      {
        targets: 5,
        width: '10%',
        orderable: false,
        searchable: false,
        className: 'text-center align-middle',
        render: function (data, type, row, meta) {
          // meta.row 로 index 얻을 수 있지만,
          // 나중에 클릭 시 DataTables에서 row 데이터 그대로 가져올 거라 index 안 써도 됨
          return `
            <button type="button"
                    class="btn btn-sm btn-outline-primary ptp-detail-btn">
              상세보기
            </button>
          `;
        }
      }
    ],
    initComplete: function () {
      console.log("📊 PTP DataTable 초기화 완료");
    }
  });

  // =========================
  // 2. 상세보기 버튼 클릭 이벤트
  // =========================
  $('#ptp_summary_table tbody').on('click', '.ptp-detail-btn', function () {
    const tr = $(this).closest('tr');
    const rowData = table.row(tr).data();

    if (!rowData) {
      console.warn("선택된 행 데이터가 없습니다.");
      return;
    }

    const hostname = rowData.hostname || rowData.device_name || '-';
    const details = Array.isArray(rowData.details) ? rowData.details : [];

    // 모달 제목
    $detailTitle.text(`[${hostname}] PTP 상세 정보`);

    // 기존 상세 내용 초기화
    $detailBody.empty();

    if (details.length === 0) {
      // 상세 데이터 없을 때
      const emptyRow = `
        <tr>
          <td class="text-center" colspan="6">상세 데이터가 없습니다.</td>
        </tr>
      `;
      $detailBody.append(emptyRow);
    } else {
      // 상세 데이터 채우기
      details.forEach(function (d) {
        const iface = d.interface || d.port || '-';
        const time = d.time || '-';
        const offset = (d.offset !== undefined && d.offset !== null) ? d.offset : '-';
        const delay = (d.delay !== undefined && d.delay !== null) ? d.delay : '-';
        const jitter = (d.jitter !== undefined && d.jitter !== null) ? d.jitter : '-';
        const seqId = (d.seq_id !== undefined && d.seq_id !== null) ? d.seq_id : '-';

        const detailRow = `
          <tr>
            <td class="text-center">${iface}</td>
            <td class="text-center">${time}</td>
            <td class="text-center">${offset}</td>
            <td class="text-center">${delay}</td>
            <td class="text-center">${jitter}</td>
            <td class="text-center">${seqId}</td>
          </tr>
        `;
        $detailBody.append(detailRow);
      });
    }

    // 부트스트랩 5 모달 열기
    const modal = new bootstrap.Modal($detailModal[0]);
    modal.show();
  });

  // =========================
  // 3. 기존 modal_mroute 버튼 로직 (필요하면 유지)
  // =========================
  const modalEl = document.getElementById('modal_mroute');
  if (modalEl) {
    const modalInstance = new bootstrap.Modal(modalEl);
    const modal_body = modalEl.querySelector('.modal-body p');
    const modal_title = document.getElementById('modal_title');

    document.querySelectorAll('.btn').forEach(button => {
      button.addEventListener('click', function () {
        if (this.id === 'btn_mroute') {
          const infoContents = this.dataset.info || "";
          const infoTitle = this.dataset.title || "Modal title";
          const html_infoText = infoContents.replace(/\\r\\n|\\n|\\r/g, '<br>');
          modal_body.innerHTML = html_infoText;
          modal_title.innerHTML = infoTitle;
          modalInstance.show();
        }
      });
    });
  }
});
