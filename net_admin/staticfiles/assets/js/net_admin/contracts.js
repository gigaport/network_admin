(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var loadingStartTime = Date.now();

    var initTable = function() {
        const data_back = document.getElementById("back_data");
        const currentPath = data_back ? data_back.dataset.submenu : 'network_contracts';

        var table = $('#contracts_table').DataTable({
            responsive: true,
            paging: false,
            searching: true,
            ordering: true,
            buttons: [
                {
                    extend: 'excel',
                    text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
                    className: 'btn btn-success btn-sm',
                    title: '네트워크계약현황_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: {
                            page: 'all'
                        }
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '네트워크계약현황_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: {
                            page: 'all'
                        }
                    }
                },
                {
                    extend: 'copy',
                    text: '<i class="fa-solid fa-copy me-2"></i>복사',
                    className: 'btn btn-secondary btn-sm',
                    exportOptions: {
                        columns: ':visible',
                        modifier: {
                            page: 'all'
                        }
                    }
                }
            ],
            ajax: {
                url: '/information/init',
                type: 'GET',
                data: {
                    sub_menu: currentPath
                },
                dataSrc: function(json) {
                    console.log('API Response:', json);
                    // 통계 업데이트
                    updateStatistics(json);
                    // API가 배열을 직접 반환하므로 그대로 사용
                    return json;
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    console.error('Response:', xhr.responseText);
                    $('#table-loading-overlay').fadeOut(300);
                }
            },
            columns: [
                { data: '번호' },
                { data: 'key_code' },
                { data: '지역' },
                { data: '유형' },
                { data: '회원사명' },
                { data: '회선분류' },
                { data: '계약유형' },
                { data: '계약체결일' },
                { data: '약정기간' },
                { data: '약정만료일' },
                { data: '계약금액' },
                { data: '추가신청금액' },
                { data: '계약금액합계' },
                { data: '안내' },
                { data: '내부검토' },
                { data: '계약착수' },
                { data: '날인대기' },
                { data: '계약완료' },
                { data: '비고' }
            ],
            columnDefs: [
                {
                    targets: 0, // 번호
                    width: '2.5%',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 1, // KEY
                    width: '4%',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 2, // 지역
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        if (data === '국내') {
                            return '<span class="badge badge-phoenix badge-phoenix-primary">국내</span>';
                        } else if (data === '해외') {
                            return '<span class="badge badge-phoenix badge-phoenix-info">해외</span>';
                        }
                        return data;
                    }
                },
                {
                    targets: 3, // 유형
                    width: '5%',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 4, // 회원사명
                    width: '7%',
                    className: 'text-start py-2 align-middle'
                },
                {
                    targets: 5, // 회선분류
                    width: '8%',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 6, // 계약유형
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        if (data === '본계약') {
                            return '<span class="badge badge-phoenix badge-phoenix-success">본계약</span>';
                        } else if (data === '추가신청') {
                            return '<span class="badge badge-phoenix badge-phoenix-warning">추가신청</span>';
                        }
                        return data;
                    }
                },
                {
                    targets: 7, // 계약체결일
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return new Date(data).toISOString().slice(0, 10);
                    }
                },
                {
                    targets: 8, // 약정기간
                    width: '4%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return data + '개월';
                    }
                },
                {
                    targets: 9, // 약정만료일
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return new Date(data).toISOString().slice(0, 10);
                    }
                },
                {
                    targets: 10, // 계약금액
                    width: '6%',
                    className: 'text-end py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return data.toLocaleString();
                    }
                },
                {
                    targets: 11, // 추가신청금액
                    width: '6%',
                    className: 'text-end py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return data.toLocaleString();
                    }
                },
                {
                    targets: 12, // 계약금액합계
                    width: '6%',
                    className: 'text-end py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return data.toLocaleString();
                    }
                },
                {
                    targets: [13, 14, 15, 16, 17], // 진행상태 (안내, 내부검토, 계약착수, 날인대기, 계약완료)
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (data === 'O') {
                            return '<span class="badge badge-phoenix badge-phoenix-success">O</span>';
                        }
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">-</span>';
                    }
                },
                {
                    targets: 18, // 비고
                    width: '11%',
                    className: 'text-start py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        if (data.length > 40) {
                            return '<span title="' + data + '">' + data.substring(0, 40) + '...</span>';
                        }
                        return data;
                    }
                }
            ],
            initComplete: function(settings, json) {
                // 로딩 완료 후 오버레이 숨기기
                var loadingTime = Date.now() - loadingStartTime;
                console.log('테이블 로딩 완료. 소요 시간:', loadingTime + 'ms');

                setTimeout(function() {
                    $('#table-loading-overlay').fadeOut(300);
                }, 300);

                // Export 버튼을 우측 상단에 추가
                table.buttons().container().appendTo('#export-buttons');
            }
        });

        // tfoot의 각 열에 검색 입력 필드 추가
        $('#contracts_table tfoot th').each(function(i) {
            var title = $(this).text();
            // 진행 상태 컬럼들(안내~계약완료: 13~17)은 드롭다운 선택
            if (i >= 13 && i <= 17) {
                $(this).html('<select class="form-control form-control-sm"><option value="">전체</option><option value="O">O</option></select>');
            } else {
                $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" />');
            }
        });

        // 개별 열 검색 기능 적용
        table.columns().every(function() {
            var that = this;
            var columnIndex = this.index();

            $('input, select', this.footer()).on('keyup change', function() {
                if (that.search() !== this.value) {
                    that.search(this.value).draw();
                }
            });
        });

        // 테이블 행 클릭 이벤트
        $('#contracts_table tbody').on('click', 'tr', function() {
            var data = table.row(this).data();
            if (data) {
                showContractModal(data);
            }
        });

        return table;
    };

    // 통계 업데이트 함수
    var updateStatistics = function(data) {
        if (!data || data.length === 0) {
            return;
        }

        var totalCount = data.length;
        var completeCount = data.filter(item => item.계약완료 === 'O').length;
        var domesticCount = data.filter(item => item.지역 === '국내').length;
        var overseasCount = data.filter(item => item.지역 === '해외').length;

        // 총 계약금액 계산 (계약금액 + 추가신청금액 또는 계약금액합계 사용)
        var totalAmount = data.reduce((sum, item) => {
            var amount = 0;
            if (item.계약금액합계) {
                amount = item.계약금액합계;
            } else {
                amount = (item.계약금액 || 0) + (item.추가신청금액 || 0);
            }
            return sum + amount;
        }, 0);

        $('#total-count').text(totalCount);
        $('#total-amount').text((totalAmount / 100000000).toFixed(1) + '억');
        $('#complete-count').text(completeCount);
        $('#domestic-count').text(domesticCount);
        $('#overseas-count').text(overseasCount);
    };

    // 계약 상세 모달 표시
    var showContractModal = function(data) {
        console.log('Opening modal with data:', data);

        // 모달 제목 설정
        $('#contractModalLabel').text('계약 상세 정보 - ' + (data.회원사명 || ''));

        // 폼 데이터 채우기
        $('#contract_id').val(data.id);
        $('#edit_번호').val(data.번호 || '');
        $('#edit_key_code').val(data.key_code || '');
        $('#edit_지역').val(data.지역 || '');
        $('#edit_유형').val(data.유형 || '');
        $('#edit_회원사명').val(data.회원사명 || '');
        $('#edit_회선분류').val(data.회선분류 || '');
        $('#edit_계약유형').val(data.계약유형 || '');
        $('#edit_안내').val(data.안내 || '');
        $('#edit_내부검토').val(data.내부검토 || '');
        $('#edit_계약착수').val(data.계약착수 || '');
        $('#edit_날인대기').val(data.날인대기 || '');
        $('#edit_계약완료').val(data.계약완료 || '');
        $('#edit_완료보고문서번호').val(data.완료보고문서번호 || '');

        // 날짜 필드 처리
        if (data.계약체결일) {
            $('#edit_계약체결일').val(data.계약체결일.split('T')[0]);
        } else {
            $('#edit_계약체결일').val('');
        }

        if (data.추가체결일) {
            $('#edit_추가체결일').val(data.추가체결일.split('T')[0]);
        } else {
            $('#edit_추가체결일').val('');
        }

        if (data.약정만료일) {
            $('#edit_약정만료일').val(data.약정만료일.split('T')[0]);
        } else {
            $('#edit_약정만료일').val('');
        }

        $('#edit_약정기간').val(data.약정기간 || '');
        $('#edit_계약금액').val(data.계약금액 || '');
        $('#edit_추가신청금액').val(data.추가신청금액 || '');
        $('#edit_계약금액합계').val(data.계약금액합계 || '');
        $('#edit_비고').val(data.비고 || '');

        // 모달 표시
        var modal = new bootstrap.Modal(document.getElementById('contractModal'));
        modal.show();
    };

    // 계약 정보 저장
    var saveContract = function() {
        var contractId = $('#contract_id').val();

        if (!contractId) {
            alert('계약 ID가 없습니다.');
            return;
        }

        // 폼 데이터 수집
        var formData = {
            '번호': $('#edit_번호').val() ? parseInt($('#edit_번호').val()) : null,
            'key_code': $('#edit_key_code').val() || null,
            '지역': $('#edit_지역').val() || null,
            '유형': $('#edit_유형').val() || null,
            '회원사명': $('#edit_회원사명').val() || null,
            '회선분류': $('#edit_회선분류').val() || null,
            '계약유형': $('#edit_계약유형').val() || null,
            '안내': $('#edit_안내').val() || null,
            '내부검토': $('#edit_내부검토').val() || null,
            '계약착수': $('#edit_계약착수').val() || null,
            '날인대기': $('#edit_날인대기').val() || null,
            '계약완료': $('#edit_계약완료').val() || null,
            '완료보고문서번호': $('#edit_완료보고문서번호').val() || null,
            '계약체결일': $('#edit_계약체결일').val() || null,
            '추가체결일': $('#edit_추가체결일').val() || null,
            '약정기간': $('#edit_약정기간').val() ? parseInt($('#edit_약정기간').val()) : null,
            '약정만료일': $('#edit_약정만료일').val() || null,
            '계약금액': $('#edit_계약금액').val() ? parseInt($('#edit_계약금액').val()) : null,
            '추가신청금액': $('#edit_추가신청금액').val() ? parseInt($('#edit_추가신청금액').val()) : null,
            '계약금액합계': $('#edit_계약금액합계').val() ? parseInt($('#edit_계약금액합계').val()) : null,
            '비고': $('#edit_비고').val() || null
        };

        // API 호출
        $.ajax({
            url: '/information/update_contract',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                id: contractId,
                data: formData
            }),
            success: function(response) {
                alert('저장되었습니다.');
                $('#contractModal').modal('hide');
                // 테이블 새로고침
                location.reload();
            },
            error: function(xhr, status, error) {
                console.error('Save error:', error);
                alert('저장에 실패했습니다: ' + (xhr.responseText || error));
            }
        });
    };

    // 계약 정보 삭제
    var deleteContract = function() {
        var contractId = $('#contract_id').val();

        if (!contractId) {
            alert('계약 ID가 없습니다.');
            return;
        }

        if (!confirm('정말 삭제하시겠습니까?')) {
            return;
        }

        // API 호출
        $.ajax({
            url: '/information/delete_contract',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                id: contractId
            }),
            success: function(response) {
                alert('삭제되었습니다.');
                $('#contractModal').modal('hide');
                // 테이블 새로고침
                location.reload();
            },
            error: function(xhr, status, error) {
                console.error('Delete error:', error);
                alert('삭제에 실패했습니다: ' + (xhr.responseText || error));
            }
        });
    };

    // DOM이 준비되면 테이블 초기화
    $(document).ready(function() {
        var table = initTable();

        // 저장 버튼 클릭 이벤트
        $('#saveBtn').on('click', function() {
            saveContract();
        });

        // 삭제 버튼 클릭 이벤트
        $('#deleteBtn').on('click', function() {
            deleteContract();
        });

        // 요약 카드 호버 애니메이션 강제 적용 (브라우저 캐시 우회)
        const summaryCards = document.querySelectorAll('.summary-card');
        summaryCards.forEach(card => {
            // 기본 스타일 설정
            card.style.transition = 'all 0.3s ease';
            card.style.cursor = 'pointer';

            // 호버 이벤트 리스너
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-4px)';
                this.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';

                // 아이콘 애니메이션
                const icon = this.querySelector('.icon-wrapper');
                if (icon) {
                    icon.style.transition = 'transform 0.3s ease';
                    icon.style.transform = 'scale(1.1)';
                }

                // 숫자 색상 변경
                const value = this.querySelector('.card-value');
                if (value) {
                    value.style.transition = 'color 0.3s ease';
                    value.style.color = '#6366f1';
                }
            });

            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
                this.style.boxShadow = '';

                // 아이콘 원상복구
                const icon = this.querySelector('.icon-wrapper');
                if (icon) {
                    icon.style.transform = 'scale(1)';
                }

                // 숫자 색상 원상복구
                const value = this.querySelector('.card-value');
                if (value) {
                    value.style.color = '#1f2937';
                }
            });
        });
    });

}));
