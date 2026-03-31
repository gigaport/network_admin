(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var productsTable = null;

    var initTable = function() {
        var loadingSpinner = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status" style="width:2rem;height:2rem;"><span class="visually-hidden">Loading...</span></div><div class="mt-2 text-muted small">데이터를 불러오는 중...</div></div>';

        productsTable = $('#productsTable').DataTable({
            responsive: true,
            paging: true,
            pageLength: 100,
            searching: true,
            ordering: true,
            language: {
                search: "검색:",
                lengthMenu: "페이지당 _MENU_ 개씩 표시",
                info: "전체 _TOTAL_개 중 _START_-_END_개 표시",
                infoEmpty: " ",
                infoFiltered: "(전체 _MAX_개 중 필터링됨)",
                paginate: {
                    first: "처음",
                    last: "마지막",
                    next: "다음",
                    previous: "이전"
                },
                emptyTable: loadingSpinner,
                zeroRecords: "검색 결과가 없습니다",
                loadingRecords: loadingSpinner
            },
            dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6 text-end"B>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            buttons: [
                {
                    extend: 'excel',
                    text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
                    className: 'btn btn-success btn-sm',
                    title: '시세상품정보_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '시세상품정보_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
                    }
                },
                {
                    extend: 'copy',
                    text: '<i class="fa-solid fa-copy me-2"></i>복사',
                    className: 'btn btn-secondary btn-sm',
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
                    }
                }
            ],
            ajax: {
                url: '/sise_products/get_products',
                type: 'GET',
                dataSrc: function(json) {
                    console.log('API Response:', json);
                    if (json.success) {
                        updateFilters(json.data);
                        return json.data;
                    } else {
                        showAlert('데이터 로드 실패: ' + json.error, 'danger');
                        return [];
                    }
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    console.error('Response:', xhr.responseText);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'id' },
                { data: 'product_name' },
                { data: 'line_speed' },
                { data: 'data_format' },
                { data: 'operation_ip1' },
                { data: 'operation_ip2' },
                { data: 'test_ip' },
                { data: 'dr_ip' },
                { data: 'retransmit_port' },
                { data: 'channel_count' },
                { data: 'created_at' },
                { data: 'updated_at' },
                { data: null, defaultContent: '' }
            ],
            columnDefs: [
                {
                    targets: 0, // ID
                    width: '50px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 1, // 상품명
                    width: '100px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 회선속도
                    width: '80px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 3, // 데이터형식
                    width: '90px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // 운영IP1
                    width: '120px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return data || '-';
                    }
                },
                {
                    targets: 5, // 운영IP2
                    width: '120px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return data || '-';
                    }
                },
                {
                    targets: 6, // 테스트IP
                    width: '120px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return data || '-';
                    }
                },
                {
                    targets: 7, // DR IP
                    width: '120px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return data || '-';
                    }
                },
                {
                    targets: 8, // 재전송포트
                    width: '80px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return data || '-';
                    }
                },
                {
                    targets: 9, // 채널수
                    width: '60px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-success">' + data + '</span>';
                    }
                },
                {
                    targets: 10, // 생성일시
                    width: '130px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 11, // 수정일시
                    width: '130px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 12, // 작업
                    width: '90px',
                    className: 'text-center py-2 align-middle white-space-nowrap',
                    orderable: false,
                    render: function(data, type, row) {
                        return '<button onclick="editProduct(' + row.id + ')" title="수정" style="width:28px; height:28px; border:none; border-radius:6px; background:transparent; color:#94a3b8; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; transition:color 0.15s; margin-right:2px;" onmouseenter="this.style.color=\'#4f46e5\'" onmouseleave="this.style.color=\'#94a3b8\'">' +
                            '<i class="fas fa-pen" style="font-size:0.65rem;"></i></button>' +
                            '<button onclick="deleteProduct(' + row.id + ')" title="삭제" style="width:28px; height:28px; border:none; border-radius:6px; background:transparent; color:#94a3b8; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; transition:color 0.15s;" onmouseenter="this.style.color=\'#dc2626\'" onmouseleave="this.style.color=\'#94a3b8\'">' +
                            '<i class="fas fa-trash-alt" style="font-size:0.65rem;"></i></button>';
                    }
                }
            ],
            initComplete: function(settings) {
                settings.oLanguage.sEmptyTable = '검색 결과가 없습니다';
                settings.oLanguage.sInfoEmpty = '데이터가 없습니다';
            }
        });

        // 행 클릭 시 수정 모달 열기 (버튼 클릭은 제외)
        $('#productsTable tbody').on('click', 'tr', function(e) {
            if ($(e.target).closest('button').length) return;
            var data = productsTable.row(this).data();
            if (data) editProduct(data.id);
        });

        // 커스텀 필터 연동
        setupCustomFilters();
    };

    function setupCustomFilters() {
        // 통합 검색
        $('#searchInput').on('input', function() {
            productsTable.search(this.value).draw();
        });

        // 회선속도 필터
        $('#speedFilter').on('change', function() {
            var value = $(this).val();
            if (value) {
                productsTable.column(2).search('^' + value + '$', true, false).draw();
            } else {
                productsTable.column(2).search('').draw();
            }
        });

        // 데이터형식 필터
        $('#formatFilter').on('change', function() {
            var value = $(this).val();
            if (value) {
                productsTable.column(3).search('^' + value + '$', true, false).draw();
            } else {
                productsTable.column(3).search('').draw();
            }
        });
    }

    function updateFilters(data) {
        // 회선속도 필터 업데이트
        var speeds = [...new Set(data.map(item => item.line_speed))].filter(Boolean).sort();
        var speedFilter = $('#speedFilter');
        speedFilter.html('<option value="">전체</option>');
        speeds.forEach(function(speed) {
            speedFilter.append('<option value="' + speed + '">' + speed + '</option>');
        });

        // 데이터형식 필터 업데이트
        var formats = [...new Set(data.map(item => item.data_format))].filter(Boolean).sort();
        var formatFilter = $('#formatFilter');
        formatFilter.html('<option value="">전체</option>');
        formats.forEach(function(format) {
            formatFilter.append('<option value="' + format + '">' + format + '</option>');
        });
    }

    window.resetFilters = function() {
        $('#searchInput').val('');
        $('#speedFilter').val('');
        $('#formatFilter').val('');
        if (productsTable) {
            productsTable.search('').columns().search('').draw();
        }
    };

    window.refreshTable = function() {
        console.log('[DEBUG] refreshTable 호출됨');

        // 스피너 표시
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span>' +
            '</div></div>');
        $('body').append(spinner);

        resetFilters();
        if (productsTable) {
            productsTable.ajax.reload(function(json) {
                console.log('[DEBUG] 데이터 새로고침 완료:', json);
                spinner.remove();
            }, false);
        } else {
            console.error('[DEBUG] productsTable이 초기화되지 않음');
            spinner.remove();
            showAlert('테이블이 초기화되지 않았습니다.', 'danger');
        }
    };

    window.showCreateModal = function() {
        // 폼 초기화
        $('#createForm')[0].reset();

        var modal = new bootstrap.Modal(document.getElementById('createModal'));
        modal.show();
    };

    window.saveCreate = function() {
        var data = {
            product_name: $('#create_product_name').val().trim(),
            line_speed: $('#create_line_speed').val().trim(),
            data_format: $('#create_data_format').val().trim(),
            operation_ip1: $('#create_operation_ip1').val().trim(),
            operation_ip2: $('#create_operation_ip2').val().trim(),
            test_ip: $('#create_test_ip').val().trim(),
            dr_ip: $('#create_dr_ip').val().trim(),
            retransmit_port: $('#create_retransmit_port').val().trim()
        };

        if (!data.product_name || !data.line_speed || !data.data_format) {
            showAlert('필수 필드를 모두 입력해주세요.', 'warning');
            return;
        }

        fetch('/sise_products/create_product', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert('추가가 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('createModal')).hide();
                refreshTable();
            } else {
                showAlert('추가 실패: ' + result.error, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('추가 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.editProduct = function(id) {
        var rowData = productsTable.rows().data().toArray();
        var product = rowData.find(item => item.id === id);
        if (!product) return;

        $('#edit_id').val(product.id);
        $('#edit_product_name').val(product.product_name);
        $('#edit_line_speed').val(product.line_speed);
        $('#edit_data_format').val(product.data_format);
        $('#edit_operation_ip1').val(product.operation_ip1);
        $('#edit_operation_ip2').val(product.operation_ip2);
        $('#edit_test_ip').val(product.test_ip);
        $('#edit_dr_ip').val(product.dr_ip);
        $('#edit_retransmit_port').val(product.retransmit_port);

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            product_name: $('#edit_product_name').val().trim(),
            line_speed: $('#edit_line_speed').val().trim(),
            data_format: $('#edit_data_format').val().trim(),
            operation_ip1: $('#edit_operation_ip1').val().trim(),
            operation_ip2: $('#edit_operation_ip2').val().trim(),
            test_ip: $('#edit_test_ip').val().trim(),
            dr_ip: $('#edit_dr_ip').val().trim(),
            retransmit_port: $('#edit_retransmit_port').val().trim()
        };

        if (!data.product_name || !data.line_speed || !data.data_format) {
            showAlert('필수 필드를 모두 입력해주세요.', 'warning');
            return;
        }

        fetch('/sise_products/update_product', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert('수정이 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                refreshTable();
            } else {
                showAlert('수정 실패: ' + result.error, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('수정 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.deleteProduct = function(id) {
        var rowData = productsTable.rows().data().toArray();
        var product = rowData.find(item => item.id === id);
        if (!product) return;

        if (!confirm(product.product_name + '을(를) 삭제하시겠습니까?\n\n※ 주의: 이 상품과 연결된 모든 채널 정보도 함께 삭제됩니다.')) {
            return;
        }

        fetch('/sise_products/delete_product', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: id })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert('삭제가 완료되었습니다.', 'success');
                refreshTable();
            } else {
                showAlert('삭제 실패: ' + result.error, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('삭제 중 오류가 발생했습니다.', 'danger');
        });
    };

    function showAlert(message, type) {
        var alertDiv = $('<div></div>')
            .addClass('alert alert-' + type + ' alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3')
            .css('zIndex', '9999')
            .html(message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>');

        $('body').append(alertDiv);

        setTimeout(function() {
            alertDiv.remove();
        }, 3000);
    }

    // 페이지 로드 시 초기화
    $(document).ready(function() {
        initTable();
    });

}));
