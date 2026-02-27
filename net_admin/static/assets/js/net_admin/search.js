(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var searchTimer = null;
    var searchInput = null;
    var searchDropdown = null;
    var searchResultsContainer = null;
    var isSearchOpen = false;

    var categoryConfig = {
        purchases:       { icon: 'fa-file-invoice',   label: '매입내역',   color: '#0d9488', url: '/purchase_contract' },
        revenue:         { icon: 'fa-chart-line',     label: '매출내역',   color: '#ef4444', url: '/revenue_summary' },
        member_circuits: { icon: 'fa-sitemap',        label: '회선내역',   color: '#f97316', url: '/circuits' },
        circuits:        { icon: 'fa-network-wired',  label: '회선',       color: '#6366f1', url: '/circuits' },
        subscribers:     { icon: 'fa-building',       label: '회원사',     color: '#0ea5e9', url: '/subscriber_codes' },
        contracts:       { icon: 'fa-file-contract',  label: '계약',       color: '#10b981', url: '/network_contracts' },
        addresses:       { icon: 'fa-location-dot',   label: '주소',       color: '#f59e0b', url: '/subscriber_address' },
        products:        { icon: 'fa-cube',           label: '시세상품',   color: '#8b5cf6', url: '/sise_products' },
        fees:            { icon: 'fa-won-sign',       label: '요금',       color: '#ec4899', url: '/fee_schedule' }
    };

    function debounce(fn, ms) {
        return function() {
            var args = arguments;
            var context = this;
            clearTimeout(searchTimer);
            searchTimer = setTimeout(function() { fn.apply(context, args); }, ms);
        };
    }

    function performSearch(query) {
        if (!query || query.trim().length < 2) {
            renderEmpty();
            return;
        }

        renderLoading();

        fetch('/search?q=' + encodeURIComponent(query.trim()))
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.success) {
                    renderSearchResults(data);
                } else {
                    renderError();
                }
            })
            .catch(function(err) {
                console.error('Search error:', err);
                renderError();
            });
    }

    function renderLoading() {
        if (!searchResultsContainer) return;
        searchResultsContainer.innerHTML =
            '<div class="text-center py-4">' +
            '  <div class="spinner-border spinner-border-sm text-primary" role="status"></div>' +
            '  <div class="mt-2" style="font-size: 0.75rem; color: #64748b;">검색 중...</div>' +
            '</div>';
        showDropdown();
    }

    function renderEmpty() {
        if (!searchResultsContainer) return;
        searchResultsContainer.innerHTML =
            '<div class="text-center py-4">' +
            '  <i class="fas fa-search" style="font-size: 1.5rem; color: #cbd5e1;"></i>' +
            '  <div class="mt-2" style="font-size: 0.75rem; color: #94a3b8;">2글자 이상 입력하세요</div>' +
            '</div>';
        showDropdown();
    }

    function renderError() {
        if (!searchResultsContainer) return;
        searchResultsContainer.innerHTML =
            '<div class="text-center py-4">' +
            '  <i class="fas fa-exclamation-circle" style="font-size: 1.5rem; color: #ef4444;"></i>' +
            '  <div class="mt-2" style="font-size: 0.75rem; color: #ef4444;">검색 중 오류가 발생했습니다</div>' +
            '</div>';
    }

    function renderNoResults(query) {
        if (!searchResultsContainer) return;
        searchResultsContainer.innerHTML =
            '<div class="text-center py-4">' +
            '  <i class="fas fa-search" style="font-size: 1.5rem; color: #cbd5e1;"></i>' +
            '  <div class="mt-2" style="font-size: 0.8rem; color: #64748b;">"<strong>' + escapeHtml(query) + '</strong>" 검색 결과가 없습니다</div>' +
            '</div>';
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }

    function highlightMatch(text, query) {
        if (!text || !query) return text || '';
        var escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        var regex = new RegExp('(' + escaped + ')', 'gi');
        return escapeHtml(text).replace(regex, '<mark style="background:#fef08a;padding:0 1px;border-radius:2px;">$1</mark>');
    }

    function renderSearchResults(data) {
        if (!searchResultsContainer) return;

        if (data.total_count === 0) {
            renderNoResults(data.query);
            return;
        }

        var html = '';

        // 총 결과 수 헤더
        html += '<div style="padding: 8px 16px; font-size: 0.7rem; color: #64748b; border-bottom: 1px solid #e2e8f0;">';
        html += '  <strong style="color: #1e293b;">' + data.total_count + '</strong>건 검색됨';
        html += '</div>';

        var categories = ['purchases', 'revenue', 'member_circuits', 'circuits', 'subscribers', 'contracts', 'addresses', 'products', 'fees'];

        categories.forEach(function(cat) {
            var catData = data.results[cat];
            if (!catData || catData.total === 0) return;

            var cfg = categoryConfig[cat];

            // 카테고리 헤더
            html += '<div style="padding: 8px 16px 4px; display: flex; align-items: center; gap: 6px;">';
            html += '  <i class="fas ' + cfg.icon + '" style="font-size: 0.65rem; color: ' + cfg.color + ';"></i>';
            html += '  <span style="font-size: 0.7rem; font-weight: 600; color: ' + cfg.color + ';">' + cfg.label + '</span>';
            html += '  <span style="font-size: 0.6rem; color: #94a3b8; margin-left: 2px;">(' + catData.total + '건)</span>';
            html += '</div>';

            // 결과 항목
            catData.items.forEach(function(item) {
                var title = highlightMatch(item.title || '-', data.query);
                var subtitle = highlightMatch(item.subtitle || '', data.query);

                html += '<a href="' + cfg.url + '" class="search-result-item" style="display: block; padding: 6px 16px 6px 36px; text-decoration: none; transition: background 0.15s;"';
                html += ' onmouseenter="this.style.background=\'#f1f5f9\'" onmouseleave="this.style.background=\'transparent\'">';
                html += '  <div style="font-size: 0.78rem; color: #1e293b; font-weight: 500; line-height: 1.3;">' + title + '</div>';
                if (subtitle) {
                    html += '  <div style="font-size: 0.65rem; color: #94a3b8; line-height: 1.3;">' + subtitle + '</div>';
                }
                html += '</a>';
            });

            // 더보기 링크
            if (catData.total > 5) {
                html += '<a href="' + cfg.url + '" style="display: block; padding: 4px 16px 8px 36px; font-size: 0.65rem; color: ' + cfg.color + '; text-decoration: none; font-weight: 500;"';
                html += ' onmouseenter="this.style.textDecoration=\'underline\'" onmouseleave="this.style.textDecoration=\'none\'">';
                html += '  ' + cfg.label + ' 전체 ' + catData.total + '건 보기 &rarr;';
                html += '</a>';
            }

            html += '<hr style="margin: 0; border-color: #f1f5f9;">';
        });

        searchResultsContainer.innerHTML = html;
        showDropdown();
    }

    function showDropdown() {
        if (searchDropdown) {
            searchDropdown.style.display = 'block';
            isSearchOpen = true;
        }
    }

    function hideDropdown() {
        if (searchDropdown) {
            searchDropdown.style.display = 'none';
            isSearchOpen = false;
        }
    }

    function initUnifiedSearch() {
        searchInput = document.getElementById('unifiedSearchInput');
        searchDropdown = document.getElementById('unifiedSearchDropdown');
        searchResultsContainer = document.getElementById('unifiedSearchResults');

        if (!searchInput || !searchDropdown || !searchResultsContainer) return;

        var clearBtn = document.getElementById('unifiedSearchClear');

        var debouncedSearch = debounce(function(e) {
            performSearch(e.target.value);
        }, 300);

        searchInput.addEventListener('input', function(e) {
            if (clearBtn) clearBtn.style.display = e.target.value.length > 0 ? 'block' : 'none';
            debouncedSearch(e);
        });

        searchInput.addEventListener('focus', function() {
            if (this.value.trim().length >= 2) {
                performSearch(this.value);
            } else {
                renderEmpty();
            }
        });

        // Esc 키로 닫기
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                hideDropdown();
                this.blur();
            }
        });

        // 외부 클릭 시 닫기
        document.addEventListener('click', function(e) {
            var searchBox = document.getElementById('unifiedSearchBox');
            if (searchBox && !searchBox.contains(e.target)) {
                hideDropdown();
            }
        });

        // 검색 input 클리어 버튼
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                searchInput.value = '';
                clearBtn.style.display = 'none';
                hideDropdown();
                searchInput.focus();
            });
        }
    }

    $(document).ready(function() { initUnifiedSearch(); });
}));
