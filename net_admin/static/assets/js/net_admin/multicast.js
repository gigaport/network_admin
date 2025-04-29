(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
  })((function () { 'use strict';
    var response_data = {};
    const data_back = document.getElementById("back_data");
    const currentPath = data_back.dataset.submenu;

    $.ajax({
        type:"GET",
        async: false,
        url:"/multicast/init",
        dataType:"json",
        data: {
            sub_menu: currentPath
        },

        success: function(response){
            response_data = response;
            
            const table = document.getElementById('multicast_table');
  
            if (table) {
                const options = {
                    page: 100,
                    pagination: {
                        item: "<li><button class='page' type='button'></button></li>"
                    },
                    item: values => {
                        const {
                            member_no,
                            member_code,
                            member_name,
                            device_name,
                            device_os,
                            products,
                            pim_rp,
                            product_cnt,
                            mroute_cnt,
                            oif_cnt,
                            min_update,
                            bfd_nbr,
                            rpf_nbr,
                            connected_server_cnt,
                            org_output,
                            alarm,
                            alarm_icon,
                            member_note,
                            check_result,
                            check_result_badge
                        } = values;
                        return `
                            <tr class="member_no hover-actions-trigger btn-reveal-trigger position-static">
                            <td class="py-2  ps-3 align-middle white-space-nowrap text-center">
                                ${member_no}
                            </td>
                            <td class="member_code py-2 align-middle text-center fw-bold">
                                ${member_code}
                            <td class="member_name py-2 align-middle text-center fw-bold">
                                <span class="text-${check_result_badge.type}">
                                ${member_name}
                                </span>
                            </td>
                            <td class="device_name py-2 align-middle text-center">
                                ${device_name}
                            </td>
                            <td class="device_os py-2 align-middle text-center">
                                ${device_os}
                            </td>
                            <td class="products py-2 align-middle text-center">
                                <span class="text-info-dark">
                                ${products}
                                </span>
                            </td>
                            <td class="pim_rp py-2 align-middle text-center fw-medium">
                                <p class="mb-0">${pim_rp}</p>
                            </td>
                            <td class="product_cnt py-2 align-middle text-center fs-8 fw-medium">
                                <span class="text-${check_result_badge.type}">
                                ${product_cnt}
                                </span>
                            </td>
                            <td class="mroute_cnt py-2 align-middle text-center fs-8 fw-medium">
                                <span class="text-${check_result_badge.type}">
                                ${mroute_cnt}
                                </span>
                            </td>
                            <td class="oif_cnt py-2 align-middle text-center fs-8 fw-medium">
                                <span class="text-${check_result_badge.type}">
                                ${oif_cnt}
                                </span>
                            </td>
                            <td class="min_uptime py-2 align-middle text-center">
                                ${min_update}
                            </td>
                            <td class="bfd_nbr py-2 align-middle text-center fw-medium">
                                업데이트예정
                            </td>
                            <td class="rpf_nbr py-2 align-middle text-center fw-medium">
                                ${rpf_nbr}
                            </td>
                            <td class="rpf_nbr py-2 align-middle text-center fw-medium">
                                <span class="text-${check_result_badge.type}">
                                ${connected_server_cnt}
                                </span>
                            </td>
                            <td class="rpf_nbr py-2 align-middle text-center fw-medium">
                                <span class="fa-solid ${alarm_icon} text-primary me-2"></span>${alarm}
                            </td>
                            <td class="rpf_nbr py-2 align-middle text-center fw-medium">
                                ${member_note}
                            </td>
                            <td class="org_output py-2 align-middle text-center fs-8 fw-medium">
                                <button id="btn_mroute" class="btn btn-phoenix-primary btn-sm" data-title=${device_name} data-info="${org_output}">mroute</button>
                            </td>
                            <td class="check_result py-2 align-middle text-center fs-8 white-space-nowrap">
                                <span class="badge fs-10 badge-phoenix badge-phoenix-${check_result_badge.type}">
                                ${check_result}
                                <span class="ms-1 ${check_result_badge.icon}" data-fa-transform="shrink-2"></span>
                                </span>
                            </td>
                            </tr>
                        `;
                        }
                    };
                    const paginationButtonNext = table.querySelector(
                    '[data-list-pagination="next"]'
                );
                const paginationButtonPrev = table.querySelector(
                '[data-list-pagination="prev"]'
                );
                const viewAll = table.querySelector('[data-list-view="*"]');
                const viewLess = table.querySelector('[data-list-view="less"]');
                const listInfo = table.querySelector('[data-list-info]');
                const listFilter = document.querySelector('[data-list-filter]');
        
                const response_data_list = new window.List(table, options, response_data);
        
                // Fallback
                response_data_list.on('updated', item => {
                    const fallback =
                        table.querySelector('.fallback') ||
                        document.getElementById(options.fallback);
            
                    if (fallback) {
                        if (item.matchingItems.length === 0) {
                        fallback.classList.remove('d-none');
                        } else {
                        fallback.classList.add('d-none');
                        }
                    }
                });
        
                const totalItem = response_data_list.items.length;
                const itemsPerPage = response_data_list.page;
                const btnDropdownClose =
                response_data_list.listContainer.querySelector('.btn-close');
                let pageQuantity = Math.ceil(totalItem / itemsPerPage);
                let numberOfcurrentItems = response_data_list.visibleItems.length;
                let pageCount = 1;
        
                btnDropdownClose &&
                btnDropdownClose.addEventListener('search.close', () =>
                    response_data_list.fuzzySearch('')
                );
        
                const updateListControls = () => {
                    listInfo &&
                        (listInfo.innerHTML = `${response_data_list.i} to ${numberOfcurrentItems} of ${totalItem}`);
                    paginationButtonPrev &&
                        togglePaginationButtonDisable(paginationButtonPrev, pageCount === 1);
                    paginationButtonNext &&
                        togglePaginationButtonDisable(
                        paginationButtonNext,
                        pageCount === pageQuantity
                        );
            
                    if (pageCount > 1 && pageCount < pageQuantity) {
                        togglePaginationButtonDisable(paginationButtonNext, false);
                        togglePaginationButtonDisable(paginationButtonPrev, false);
                    }
                };
                updateListControls();
        
                if (paginationButtonNext) {
                    paginationButtonNext.addEventListener('click', e => {
                        e.preventDefault();
                        pageCount += 1;
            
                        const nextInitialIndex = response_data_list.i + itemsPerPage;
                        nextInitialIndex <= response_data_list.size() &&
                        response_data_list.show(nextInitialIndex, itemsPerPage);
                        numberOfcurrentItems += response_data_list.visibleItems.length;
                        updateListControls();
                    });
                }
        
                if (paginationButtonPrev) {
                    paginationButtonPrev.addEventListener('click', e => {
                        e.preventDefault();
                        pageCount -= 1;
            
                        numberOfcurrentItems -= response_data_list.visibleItems.length;
                        const prevItem = response_data_list.i - itemsPerPage;
                        prevItem > 0 && response_data_list.show(prevItem, itemsPerPage);
                        updateListControls();
                    });
                }
        
                const toggleViewBtn = () => {
                    viewLess.classList.toggle('d-none');
                    viewAll.classList.toggle('d-none');
                };
        
                if (viewAll) {
                    viewAll.addEventListener('click', () => {
                        response_data_list.show(1, totalItem);
                        pageQuantity = 1;
                        pageCount = 1;
                        numberOfcurrentItems = totalItem;
                        updateListControls();
                        toggleViewBtn();
                    });
                }
                if (viewLess) {
                    viewLess.addEventListener('click', () => {
                        response_data_list.show(1, itemsPerPage);
                        pageQuantity = Math.ceil(totalItem / itemsPerPage);
                        pageCount = 1;
                        numberOfcurrentItems = response_data_list.visibleItems.length;
                        updateListControls();
                        toggleViewBtn();
                });
                }
                if (options.pagination) {
                    table.querySelector('.pagination').addEventListener('click', e => {
                        if (e.target.classList[0] === 'page') {
                        pageCount = Number(e.target.innerText);
                        updateListControls();
                        }
                    });
                }
                if (options.filter) {
                    const { key } = options.filter;
                    listFilter.addEventListener('change', e => {
                        response_data_list.filter(item => {
                        if (e.target.value === '') {
                            return true;
                        }
                        return item
                            .values()
                            [key].toLowerCase()
                            .includes(e.target.value.toLowerCase());
                        });
                    });
                }
            }
        }
    });

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
  
    const advanceAjaxTableInit = () => {
      const togglePaginationButtonDisable = (button, disabled) => {
        button.disabled = disabled;
        button.classList[disabled ? 'add' : 'remove']('disabled');
      };
      // Selectors
      
    };
  
    const { docReady } = window.phoenix.utils;
    docReady(advanceAjaxTableInit);

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
    setTimeout(function() {
        window.location.reload();
    }, 60000);

  }));
  //# sourceMappingURL=advance-ajax-table.js.map
  