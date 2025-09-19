(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
  })((function () { 'use strict';
    var response_data = {};
    const data_back = document.getElementById("back_data");
    const currentPath = data_back.dataset.submenu;

    var initTable = function() {
        var table = $('#interface_table').DataTable({
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
                    sub_menu: currentPath
                },
                // dataType: 'json',
                // success: function(response){
                //     response_data = response;
                // }
            },
            columns: [
                { data: 'device_name' }, // 0
                { data: 'device_ip' }, // 1
                { data: 'device_os' }, // 2
                { data: 'interface_no' }, // 3
                { data: 'interface_description' }, // 4
                { data: 'interface_status' }, // 5
                { data: 'interface_vlan' }, // 6
                { data: 'interface_duplex' }, // 7
                { data: 'interface_speed' }, // 8
                { data: 'interface_type' }, // 9
            ],
            columnDefs: [
                {
                    targets: 0,
                    width: '10%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fw-bold fs-8');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
                {
                    targets: 1,
                    width: '6%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
                {
                    targets: 2,
                    width: '4%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
                {
                    targets: 3,
                    width: '10%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fw-bold fs-8');
                    },
                    render: function(data, type, row, meta) {
                        let status_data = row.interface_status;

                        if (status_data.includes('connected')) {
                            return '<span class="text-primary">' + data + '</span>';
                        } else if (status_data.includes('notconnect')) {
                            return '<span class="text-danger">' + data + '</span>';
                        } else if (status_data.includes('xcvrAbsen')) {
                            return '<span class="label-warning">' + data + '</span>';
                        } else if (status_data.includes('disabled')) {
                            return '<span class="label-warning">' + data + '</span>';
                        } else {
                            return data;
                        }
                    }
                },
                {
                    targets: 4,
                    width: '20%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fs-8');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
                {
                    targets: 5,
                    width: '10%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fs-8 fw-bold');
                    },
                    render: function(data, type, row, meta) {
                        var status = {
							'connected': {'title': 'connected', 'class': 'primary'},
							'notconnect': {'title': 'notconnect', 'class': 'danger'},
							'xcvrAbsen': {'title': 'xcvrAbsen', 'class': 'warning'},
							'disabled': {'title': 'disabled', 'class': 'warning'}
						};
						if (typeof status[data] == 'undefined') {
							return data;
						}
						return '<span class="badge fs-10 badge-phoenix badge-phoenix-' + status[data].class + '">' + status[data].title + '</span>';
                    }
                },
                {
                    targets: 6,
                    width: '10%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fs-8');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
                {
                    targets: 7,
                    width: '10%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fs-8');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
                {
                    targets: 8,
                    width: '10%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fs-8');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
                {
                    targets: 9,
                    width: '10%',
                    createdCell: function(td, cellData, rowData, row, col) {
                        $(td).addClass('text-center device_name py-2 align-middle text-center fs-8');
                    },
                    render: function(data, type, row, meta) {
                        return data;
                    }
                },
            ],
            initComplete: function(){
                console.log("📊 DataTable has finished loading");
                table.buttons().container().appendTo('#dropdown-inline');
				this.api().columns().every(function () {
                    let column = this;
                    let title = column.footer().textContent;

                    // Create input element
                    let input = document.createElement('input');
                    input.placeholder = title;
                    column.footer().replaceChildren(input);

                    // $('thead th').eq(column.index()).append(input);
                    // $('tfoot').remove();  // 또는 hide()

                    // Event listener for user input
                    input.addEventListener('keyup', () => {
                        if (column.search() !== this.value) {
                            column.search(input.value).draw();
                        }
                    });
                });
                $("#interface_table").show();
            },
        });
    }


    // $.ajax({
    //     type:"GET",
    //     async: false,
    //     url:"/information/init",
    //     dataType:"json",
    //     data: {
    //         sub_menu: currentPath
    //     },

    //     success: function(response){
    //         response_data = response;
            
    //         const togglePaginationButtonDisable = (button, disabled) => {
    //             button.disabled = disabled;
    //             button.classList[disabled ? 'add' : 'remove']('disabled');
    //         };

    //         const table = document.getElementById('advanceAjaxTable');

    //         if (table) {
    //             const options = {
    //                 page: 100,
    //                 pagination: {
    //                     item: "<li><button class='page' type='button'></button></li>"
    //                 },
    //                 item: values => {
    //                     const {
    //                         device_name,
    //                         device_ip,
    //                         device_os,
    //                         interface_no,
    //                         interface_description,
    //                         interface_status,
    //                         interface_vlan,
    //                         interface_duplex,
    //                         interface_speed,
    //                         interface_type,
    //                         interface_class
    //                     } = values;
    //                     return `
    //                         <tr class="tr_list hover-actions-trigger btn-reveal-trigger position-static">
    //                         <td class="device_name py-2 align-middle text-center fs-8 fw-bold">
    //                             ${device_name}
    //                         </td>
    //                         <td class="device_ip py-2 align-middle text-center fs-8">
    //                             ${device_ip}
    //                         </td>
    //                         <td class="device_os py-2 align-middle text-center fs-8">
    //                             ${device_os}
    //                         </td>
    //                         <td class="interface_no py-2 align-middle text-center fs-8 fw-bold">
    //                             <span class="${interface_class}">
    //                             ${interface_no}
    //                             </span>
    //                         </td>
    //                         <td class="interface_description py-2 align-middle fs-8 text-center">
    //                             <span class="text-primary-darker">
    //                             ${interface_description}
    //                             </span>
    //                         </td>
    //                         <td class="interface_status py-2 align-middle text-center fs-8 fw-bold">
    //                             <span class="${interface_class}">
    //                             ${interface_status}
    //                             </span>
    //                         </td>
    //                         <td class="interface_vlan py-2 align-middle text-center fs-8 fw-medium">
    //                             <p class="mb-0">${interface_vlan}</p>
    //                         </td>
    //                         <td class="interface_duplex py-2 align-middle text-center fs-8">
    //                             ${interface_duplex}
    //                         </td>
    //                         <td class="interface_speed py-2 align-middle text-center fs-8 fw-medium">
    //                             ${interface_speed}
    //                         </td>
    //                         <td class="interface_type py-2 align-middle text-center fs-8 fw-medium">
    //                             ${interface_type}
    //                         </td>
    //                         </tr>
    //                     `;
    //                     }
    //                 };
    //             const paginationButtonNext = table.querySelector(
    //                 '[data-list-pagination="next"]'
    //             );
    //             const paginationButtonPrev = table.querySelector(
    //                 '[data-list-pagination="prev"]'
    //             );
    //             const viewAll = table.querySelector('[data-list-view="*"]');
    //             const viewLess = table.querySelector('[data-list-view="less"]');
    //             const listInfo = table.querySelector('[data-list-info]');
    //             const listFilter = document.querySelector('[data-list-filter]');
        
    //             const response_data_list = new window.List(table, options, response_data);
        
    //             // Fallback
    //             response_data_list.on('updated', item => {
    //                 const fallback =
    //                     table.querySelector('.fallback') ||
    //                     document.getElementById(options.fallback);
            
    //                 if (fallback) {
    //                     if (item.matchingItems.length === 0) {
    //                     fallback.classList.remove('d-none');
    //                     } else {
    //                     fallback.classList.add('d-none');
    //                     }
    //                 }
    //             });
        
    //             const totalItem = response_data_list.items.length;
    //             const itemsPerPage = response_data_list.page;
    //             const btnDropdownClose = response_data_list.listContainer.querySelector('.btn-close');
    //             let pageQuantity = Math.ceil(totalItem / itemsPerPage);
    //             let numberOfcurrentItems = response_data_list.visibleItems.length;
    //             let pageCount = 1;
        
    //             btnDropdownClose &&
    //             btnDropdownClose.addEventListener('search.close', () =>
    //                 response_data_list.fuzzySearch('')
    //             );
        
    //             const updateListControls = () => {
    //                 listInfo &&
    //                     (listInfo.innerHTML = `${response_data_list.i} to ${numberOfcurrentItems} of ${totalItem}`);
    //                 paginationButtonPrev &&
    //                     togglePaginationButtonDisable(paginationButtonPrev, pageCount === 1);
    //                 paginationButtonNext &&
    //                     togglePaginationButtonDisable(
    //                     paginationButtonNext,
    //                     pageCount === pageQuantity
    //                     );
            
    //                 if (pageCount > 1 && pageCount < pageQuantity) {
    //                     togglePaginationButtonDisable(paginationButtonNext, false);
    //                     togglePaginationButtonDisable(paginationButtonPrev, false);
    //                 }
    //             };
    //             updateListControls();
        
    //             if (paginationButtonNext) {
    //                 paginationButtonNext.addEventListener('click', e => {
    //                     e.preventDefault();
    //                     pageCount += 1;
            
    //                     const nextInitialIndex = response_data_list.i + itemsPerPage;
    //                     nextInitialIndex <= response_data_list.size() &&
    //                     response_data_list.show(nextInitialIndex, itemsPerPage);
    //                     numberOfcurrentItems += response_data_list.visibleItems.length;
    //                     updateListControls();
    //                 });
    //             }
        
    //             if (paginationButtonPrev) {
    //                 paginationButtonPrev.addEventListener('click', e => {
    //                     e.preventDefault();
    //                     pageCount -= 1;
            
    //                     numberOfcurrentItems -= response_data_list.visibleItems.length;
    //                     const prevItem = response_data_list.i - itemsPerPage;
    //                     prevItem > 0 && response_data_list.show(prevItem, itemsPerPage);
    //                     updateListControls();
    //                 });
    //             }
        
    //             const toggleViewBtn = () => {
    //                 viewLess.classList.toggle('d-none');
    //                 viewAll.classList.toggle('d-none');
    //             };
        
    //             if (viewAll) {
    //                 viewAll.addEventListener('click', () => {
    //                     response_data_list.show(1, totalItem);
    //                     pageQuantity = 1;
    //                     pageCount = 1;
    //                     numberOfcurrentItems = totalItem;
    //                     updateListControls();
    //                     toggleViewBtn();
    //                 });
    //             }
    //             if (viewLess) {
    //                 viewLess.addEventListener('click', () => {
    //                     response_data_list.show(1, itemsPerPage);
    //                     pageQuantity = Math.ceil(totalItem / itemsPerPage);
    //                     pageCount = 1;
    //                     numberOfcurrentItems = response_data_list.visibleItems.length;
    //                     updateListControls();
    //                     toggleViewBtn();
    //             });
    //             }
    //             if (options.pagination) {
    //                 table.querySelector('.pagination').addEventListener('click', e => {
    //                     if (e.target.classList[0] === 'page') {
    //                     pageCount = Number(e.target.innerText);
    //                     updateListControls();
    //                     }
    //                 });
    //             }
    //             if (options.filter) {
    //                 const { key } = options.filter;
    //                 listFilter.addEventListener('change', e => {
    //                     response_data_list.filter(item => {
    //                     if (e.target.value === '') {
    //                         return true;
    //                     }
    //                     return item
    //                         .values()
    //                         [key].toLowerCase()
    //                         .includes(e.target.value.toLowerCase());
    //                     });
    //                 });
    //             }
    //         }
    //     }
    // });

    // $('#kt_datatable tbody').on('click', 'a', function(e) {
    //     e.preventDefault(); // 기본 동작 방지
    //     console.log(received_data);
    //     // 필요한 동작 수행
    //     var route_id = $(this).text();
    //     console.log(route_id);

    //     var index = received_data.findIndex(obj => obj.subnet_rt_id === route_id);
    //     // console.log(index);
    //     var route_tables = received_data[index].subnet_rt;
    //     var subnet_name = received_data[index].subnet_name;
    //     document.getElementById("h5-subnet-routetable").innerText = 'SUBNET : ' + ' '+ subnet_name + ' || ROUTE_ID : ' + route_id;
    //     // console.log(received_data[index]);
    //     // console.log(route_tables.length);
    //     // 기존 전체 row 삭제
    //     $("#tbody-subnet-routetable tr").remove();

    //     for (var i = 0; i < route_tables.length; i++){
    //         // console.log(route_tables[i].DestinationCidrBlock);
    //         if ("TransitGatewayId" in route_tables[i]) {
    //             $('#table-subnet-routetable> tbody:last').append('<tr><td>' + route_tables[i].DestinationCidrBlock + '</td><td>' + route_tables[i].TransitGatewayId + '</td><td>' + route_tables[i].Origin + '</td><td>' + route_tables[i].State + '</td></tr>');
    //         } else {
    //             $('#table-subnet-routetable> tbody:last').append('<tr><td>' + route_tables[i].DestinationCidrBlock + '</td><td>' + route_tables[i].GatewayId + '</td><td>' + route_tables[i].Origin + '</td><td>' + route_tables[i].State + '</td></tr>');
    //         }
    //     }

    //     $('#modal-subnet-routetable').modal();
    //     // var row = table.row(tr);
    //     // var data = row.data();
    //     //
    //     // // 클릭된 링크와 관련된 행의 데이터에 접근
    //     // console.log(data);
    // });
  
    // const advanceAjaxTableInit = () => {
    //   const togglePaginationButtonDisable = (button, disabled) => {
    //     button.disabled = disabled;
    //     button.classList[disabled ? 'add' : 'remove']('disabled');
    //   };
    //   // Selectors
      
    // };
  
    // const { docReady } = window.phoenix.utils;
    // docReady(advanceAjaxTableInit);

    document.addEventListener('DOMContentLoaded', function(){
        console.log("이벤트 감지됨", this.value);
        // const searchInput = document.getElementById('search_mroute');
        // const table = document.getElementById('multicast_table');
        // const rows = table.querySelectorAll('tbody tr');

        // searchInput.addEventListener("input", function(){
        //     console.log("입력 감지됨", this.value);

        //     const keyword = this.value.trim().toLowerCase();
        //     let matchCount = 0;

        //     rows.forEach(row => {
        //         console.log("키워드", keyword);
        //         if (keyword == '교'){
        //             console.log("교로 매칭");
        //         }
        //         const rowText = row.innerHTML.replace(/\s+/g, ' ').toLowerCase();
        //         const isMatch = rowText.includes(keyword);
        //         row.computedStyleMap.display = isMatch ? "table-row" : "none";
        //         console.log({currentDisplay: row.style.dislay});
        //         if (isMatch) matchCount++;
        //     });
        // });

        let buttons = document.querySelectorAll('.btn');
        let modalEl = document.getElementById('modal_mroute');
        let modalInstance = new bootstrap.Modal(modalEl);
        let modal_body = modalEl.querySelector('.modal-body p');
        let modal_title = document.getElementById('modal_title');

        buttons.forEach(button => {
            button.addEventListener('click', function(){
                if (this.id == 'btn_mroute') {
                    let infoContents = this.dataset.info;
                    let infoTitle = this.dataset.title;
                    let html_infoText = infoContents.replace(/\\r\\n|\\n|\\n|\\r/g, '<br>');
                    modal_body.innerHTML = html_infoText;
                    modal_title.innerHTML = infoTitle;
                    modalInstance.show();
                }
            });
        });
    });
    // setTimeout(function() {
    //     window.location.reload();
    // }, 60000);

    initTable();

  }));
  //# sourceMappingURL=advance-ajax-table.js.map
  