(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var channelsTable = null;
    var productsData = []; // 상품 목록 저장

    var initTable = function() {
        var loadingSpinner = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status" style="width:2rem;height:2rem;"><span class="visually-hidden">Loading...</span></div><div class="mt-2 text-muted small">데이터를 불러오는 중...</div></div>';

        channelsTable = $('#channelsTable').DataTable({
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
                    title: '시세채널정보_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '시세채널정보_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
                    }
                },
                {
                    extend: 'copy',
                    text: '<i class="fa-solid fa-copy me-2"></i>복사',
                    className: 'btn btn-secondary btn-sm',
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
                    }
                }
            ],
            ajax: {
                url: '/sise_product_detail/get_channels',
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
                { data: 'service_type' },
                { data: 'market_type' },
                { data: 'multicast_group_ip' },
                { data: 'operation_port' },
                { data: 'test_port' },
                { data: 'operation_ip1' },
                { data: 'operation_ip2' },
                { data: 'test_ip' },
                { data: 'dr_ip' },
                { data: 'created_at' },
                { data: 'updated_at' },
                { data: null, defaultContent: '' }
            ],
            columnDefs: [
                {
                    targets: 0, // ID
                    width: '40px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 1, // 상품명
                    width: '90px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 서비스유형
                    width: '120px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 3, // 시장유형
                    width: '90px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // 멀티캐스트IP
                    width: '110px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<code style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:4px;font-size:0.8rem;font-weight:600;">' + data + '</code>';
                    }
                },
                {
                    targets: 5, // 운영포트
                    width: '80px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<code style="background:#dbeafe;color:#1e40af;padding:2px 6px;border-radius:4px;font-size:0.8rem;font-weight:600;">' + data + '</code>';
                    }
                },
                {
                    targets: 6, // 테스트포트
                    width: '80px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<code style="background:#dcfce7;color:#166534;padding:2px 6px;border-radius:4px;font-size:0.8rem;font-weight:600;">' + data + '</code>';
                    }
                },
                {
                    targets: 7, // 운영IP1
                    width: '110px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="text-muted">' + data + '</span>';
                    }
                },
                {
                    targets: 8, // 운영IP2
                    width: '110px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="text-muted">' + data + '</span>';
                    }
                },
                {
                    targets: 9, // 테스트IP
                    width: '110px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="text-muted">' + data + '</span>';
                    }
                },
                {
                    targets: 10, // DR IP
                    width: '110px',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="text-muted">' + data + '</span>';
                    }
                },
                {
                    targets: 11, // 생성일시
                    width: '120px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 12, // 수정일시
                    width: '120px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 13, // 작업
                    width: '90px',
                    className: 'text-center py-2 align-middle white-space-nowrap',
                    orderable: false,
                    render: function(data, type, row) {
                        return `
                            <button class="btn btn-sm btn-phoenix-secondary me-1" onclick="editChannel(${row.id})" title="수정">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-phoenix-danger" onclick="deleteChannel(${row.id})" title="삭제">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        `;
                    }
                }
            ],
            initComplete: function(settings) {
                settings.oLanguage.sEmptyTable = '검색 결과가 없습니다';
                settings.oLanguage.sInfoEmpty = '데이터가 없습니다';
                loadProducts();
            }
        });

        // 행 클릭 시 수정 모달 열기 (버튼 클릭은 제외)
        $('#channelsTable tbody').on('click', 'tr', function(e) {
            if ($(e.target).closest('button').length) return;
            var data = channelsTable.row(this).data();
            if (data) editChannel(data.id);
        });

        // 커스텀 필터 연동
        setupCustomFilters();
    };

    function setupCustomFilters() {
        // 통합 검색
        $('#searchInput').on('input', function() {
            channelsTable.search(this.value).draw();
        });

        // 상품 필터
        $('#productFilter').on('change', function() {
            var value = $(this).val();
            if (value) {
                channelsTable.column(1).search('^' + value + '$', true, false).draw();
            } else {
                channelsTable.column(1).search('').draw();
            }
        });

        // 시장유형 필터
        $('#marketFilter').on('change', function() {
            var value = $(this).val();
            if (value) {
                channelsTable.column(3).search('^' + value + '$', true, false).draw();
            } else {
                channelsTable.column(3).search('').draw();
            }
        });
    }

    function updateFilters(data) {
        // 상품명 필터 업데이트
        var products = [...new Set(data.map(item => item.product_name))].filter(Boolean).sort();
        var productFilter = $('#productFilter');
        productFilter.html('<option value="">전체</option>');
        products.forEach(function(product) {
            productFilter.append('<option value="' + product + '">' + product + '</option>');
        });

        // 시장유형 필터 업데이트
        var markets = [...new Set(data.map(item => item.market_type))].filter(Boolean).sort();
        var marketFilter = $('#marketFilter');
        marketFilter.html('<option value="">전체</option>');
        markets.forEach(function(market) {
            marketFilter.append('<option value="' + market + '">' + market + '</option>');
        });
    }

    function loadProducts() {
        // 상품 목록을 불러와서 모달의 select box에 채움
        fetch('/sise_products/get_products')
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    productsData = result.data;
                    updateProductSelects();
                } else {
                    console.error('상품 목록 로드 실패:', result.error);
                }
            })
            .catch(error => {
                console.error('Error loading products:', error);
            });
    }

    function updateProductSelects() {
        var createSelect = $('#create_product_id');
        var editSelect = $('#edit_product_id');

        createSelect.html('<option value="">선택하세요</option>');
        editSelect.html('<option value="">선택하세요</option>');

        productsData.forEach(function(product) {
            var option = '<option value="' + product.id + '">' + product.product_name + '</option>';
            createSelect.append(option);
            editSelect.append(option);
        });
    }

    window.resetFilters = function() {
        $('#searchInput').val('');
        $('#productFilter').val('');
        $('#marketFilter').val('');
        if (channelsTable) {
            channelsTable.search('').columns().search('').draw();
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
        if (channelsTable) {
            channelsTable.ajax.reload(function(json) {
                console.log('[DEBUG] 데이터 새로고침 완료:', json);
                spinner.remove();
            }, false);
        } else {
            console.error('[DEBUG] channelsTable이 초기화되지 않음');
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
            product_id: parseInt($('#create_product_id').val()),
            service_type: $('#create_service_type').val().trim(),
            market_type: $('#create_market_type').val().trim(),
            multicast_group_ip: $('#create_multicast_group_ip').val().trim(),
            operation_port: $('#create_operation_port').val().trim(),
            test_port: $('#create_test_port').val().trim()
        };

        if (!data.product_id || !data.service_type || !data.market_type) {
            showAlert('필수 필드를 모두 입력해주세요.', 'warning');
            return;
        }

        fetch('/sise_product_detail/create_channel', {
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

    window.editChannel = function(id) {
        var rowData = channelsTable.rows().data().toArray();
        var channel = rowData.find(item => item.id === id);
        if (!channel) return;

        $('#edit_id').val(channel.id);
        $('#edit_product_id').val(channel.product_id);
        $('#edit_service_type').val(channel.service_type);
        $('#edit_market_type').val(channel.market_type);
        $('#edit_multicast_group_ip').val(channel.multicast_group_ip);
        $('#edit_operation_port').val(channel.operation_port);
        $('#edit_test_port').val(channel.test_port);

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            product_id: parseInt($('#edit_product_id').val()),
            service_type: $('#edit_service_type').val().trim(),
            market_type: $('#edit_market_type').val().trim(),
            multicast_group_ip: $('#edit_multicast_group_ip').val().trim(),
            operation_port: $('#edit_operation_port').val().trim(),
            test_port: $('#edit_test_port').val().trim()
        };

        if (!data.product_id || !data.service_type || !data.market_type) {
            showAlert('필수 필드를 모두 입력해주세요.', 'warning');
            return;
        }

        fetch('/sise_product_detail/update_channel', {
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

    window.deleteChannel = function(id) {
        var rowData = channelsTable.rows().data().toArray();
        var channel = rowData.find(item => item.id === id);
        if (!channel) return;

        if (!confirm(channel.product_name + ' - ' + channel.service_type + ' (' + channel.market_type + ')을(를) 삭제하시겠습니까?')) {
            return;
        }

        fetch('/sise_product_detail/delete_channel', {
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
