    const paginationConfigElement = document.getElementById('paginationConfig');
    const paginationConfig = paginationConfigElement ? JSON.parse(paginationConfigElement.textContent) : {};
    const paginationPageSizeOptions = (paginationConfig.options || []).map(Number).filter(size => Number.isInteger(size) && size > 0).slice(0, 5);
    if (!paginationPageSizeOptions.length) paginationPageSizeOptions.push(10, 20, 50);
    const defaultPaginationPageSize = paginationPageSizeOptions.includes(Number(paginationConfig.default)) ? Number(paginationConfig.default) : paginationPageSizeOptions[0];

    // ============================
    // PagedTable: общий жизненный цикл вкладки с серверной пагинацией.
    // Хранит состояние, загружает данные, отбрасывает устаревшие ответы (requestId),
    // рисует таблицу и привязывает поиск, сортировку, пагинацию и фильтр избранного.
    // config: state, apiUrl, ids {body, count, info, prev, next, search, favoritesFilter?},
    //   sortAttr (атрибут кнопок сортировки), colspan, itemsKey, countLabel | formatCount(items),
    //   emptyMessage, loadingMessage, notConnectedMessage, errorFallbackMessage,
    //   defaultDirection(sort), renderRow(item) -> html, renderSummary?(data | null),
    //   filters? [{id, stateKey, param}] — необязательные фильтры-select (значение -> state -> параметр запроса)
    // ============================
    class PagedTable {
        constructor(config) {
            this.config = config;
            this.state = config.state;
            this.requestId = 0;
            this.searchTimer = null;
        }

        element(key) {
            const id = this.config.ids[key];
            return id ? document.getElementById(id) : null;
        }

        findActiveConnection() {
            return connections.find(c => String(c.id) === String(activeConnectionId));
        }

        buildParams(conn) {
            const {state, config} = this;
            const params = {
                id: conn.id,
                page: state.page,
                page_size: state.pageSize,
                search: state.search,
                sort: state.sort,
                direction: state.direction
            };
            (config.filters || []).forEach(filter => { params[filter.param] = state[filter.stateKey]; });
            if (config.ids.favoritesFilter) params.favorites_only = state.favoritesOnly;
            return params;
        }

        refresh(conn = this.findActiveConnection()) {
            const requestId = ++this.requestId;
            if (!conn || !/^\d+$/.test(String(conn.id))) {
                this.state.totalCount = 0;
                this.renderWarning(this.config.notConnectedMessage);
                return;
            }
            this.renderWarning(this.config.loadingMessage);
            connectionRequest(this.config.apiUrl, this.buildParams(conn))
                .then(data => {
                    if (requestId === this.requestId) this.render(data);
                })
                .catch(error => {
                    if (requestId === this.requestId) {
                        this.renderError(error.message || this.config.errorFallbackMessage);
                    }
                });
        }

        // После ошибки прежние итоги больше не верны: без сброса кнопка «Далее» осталась бы
        // активной по данным последней успешной загрузки, хотя подпись показывает «Страница 1 из 1».
        renderError(message) {
            this.state.page = 1;
            this.state.totalCount = 0;
            this.renderWarning(message);
        }

        renderWarning(message) {
            const tbody = this.element('body');
            const count = this.element('count');
            const info = this.element('info');
            if (count) count.textContent = 'Нет данных';
            if (info) info.textContent = 'Страница 1 из 1';
            this.config.renderSummary?.(null);
            if (tbody) tbody.innerHTML = `<tr><td colspan="${this.config.colspan}" class="text-muted">${escapeHtml(message)}</td></tr>`;
            this.updatePaginationButtons();
        }

        render(data) {
            const tbody = this.element('body');
            if (!tbody) return;
            const {state, config} = this;
            state.totalCount = Number(data.total_count) || 0;
            state.page = Number(data.page) || 1;
            state.pageSize = Number(data.page_size) || defaultPaginationPageSize;
            this.updateSortIndicators();
            config.renderSummary?.(data);
            const items = data[config.itemsKey] || [];
            const totalPages = Math.max(Math.ceil(state.totalCount / state.pageSize), 1);
            const count = this.element('count');
            const info = this.element('info');
            if (count) count.textContent = config.formatCount ? config.formatCount(items) : `${items.length} из ${state.totalCount} ${config.countLabel}`;
            if (info) info.textContent = `Страница ${state.page} из ${totalPages}`;
            tbody.innerHTML = items.length
                ? items.map(item => config.renderRow(item)).join('')
                : `<tr><td colspan="${config.colspan}" class="text-muted">${escapeHtml(config.emptyMessage)}</td></tr>`;
            this.updatePaginationButtons();
        }

        updateSortIndicators() {
            const {sortAttr} = this.config;
            document.querySelectorAll(`[${sortAttr}]`).forEach(button => {
                const isActive = button.getAttribute(sortAttr) === this.state.sort;
                button.classList.toggle('active', isActive);
                updateSortHeaderState(button, isActive, this.state.direction);
            });
        }

        // Общий хелпер updatePaginationButtons(state, prevId, nextId) из модуля страницы.
        updatePaginationButtons() {
            updatePaginationButtons(this.state, this.config.ids.prev, this.config.ids.next);
        }

        bindControls() {
            const {state, config} = this;
            const favoritesFilter = this.element('favoritesFilter');
            favoritesFilter?.addEventListener('change', () => {
                state.favoritesOnly = favoritesFilter.value === 'favorites';
                state.page = 1;
                this.refresh();
            });
            (config.filters || []).forEach(filter => {
                const select = document.getElementById(filter.id);
                select?.addEventListener('change', () => {
                    state[filter.stateKey] = select.value;
                    state.page = 1;
                    this.refresh();
                });
            });
            const searchInput = this.element('search');
            searchInput?.addEventListener('input', () => {
                clearTimeout(this.searchTimer);
                this.searchTimer = setTimeout(() => {
                    state.search = searchInput.value.trim();
                    state.page = 1;
                    this.refresh();
                }, 300);
            });
            document.querySelectorAll(`[${config.sortAttr}]`).forEach(button => {
                button.addEventListener('click', () => {
                    const sort = button.getAttribute(config.sortAttr);
                    if (state.sort === sort) {
                        state.direction = state.direction === 'asc' ? 'desc' : 'asc';
                    } else {
                        state.sort = sort;
                        state.direction = config.defaultDirection(sort);
                    }
                    state.page = 1;
                    this.refresh();
                });
            });
            this.element('prev')?.addEventListener('click', () => {
                if (state.page > 1) {
                    state.page -= 1;
                    this.refresh();
                }
            });
            this.element('next')?.addEventListener('click', () => {
                const totalPages = Math.max(Math.ceil(state.totalCount / state.pageSize), 1);
                if (state.page < totalPages) {
                    state.page += 1;
                    this.refresh();
                }
            });
            this.updateSortIndicators();
            this.updatePaginationButtons();
        }
    }

// ============================
    // STATE
    // ============================
    let connections = [];
    let activeConnectionId = null;
    let charts = {};
    let modalInstance = null;
    let connectionModalMode = 'create';
    let currentSegments = [];
    let currentSegmentsWarningHtml = '';
    let segmentsSortState = {column: 'segment', direction: 'asc'};
    let schemaSizesState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: '', favoritesOnly: false};
    let tableSizesState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: '', favoritesOnly: false};
    let viewsState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'schema_name', direction: 'asc', search: '', viewType: '', favoritesOnly: false};
    let functionsState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'schema_name', direction: 'asc', search: '', favoritesOnly: false};
    let distributionTables = [];
    let selectedDistributionTable = null;
    let distributionPickerActiveIndex = -1;
    let currentDistributionSegments = [];
    let currentDistributionTotalRows = 0;
    let distributionSortState = {column: 'segment_id', direction: 'asc'};
    let distributionRequestId = 0;
    let distributionTablesRequestId = 0;
    let activeQueriesRequestId = 0;
    let activeQueriesState = {sort: 'duration_seconds', direction: 'desc', refreshInterval: 0, timer: null, username: '', inFlight: false};
    const terminatedActiveQueryKeys = new Set();
    let activeSessionsRequestId = 0;
    let activeSessionsState = {sort: 'session_duration_seconds', direction: 'desc', refreshInterval: 0, timer: null, username: '', state: '', inFlight: false};
    const terminatedActiveSessionKeys = new Set();
    let blockingLocksRequestId = 0;
    let blockingLocksState = {refreshInterval: 0, timer: null, blockedUsername: '', blockerUsername: '', inFlight: false};
    let idleTransactionsRequestId = 0;
    let idleTransactionsState = {refreshInterval: 0, timer: null, username: '', inFlight: false};
    let maintenanceStatsState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'dead_rows', direction: 'desc', search: '', selectedTableKey: ''};
    let maintenanceStatsRequestId = 0;
    const maintenanceJobs = new Map();
    let backgroundJobsErrorNotified = false;
    let usersState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'name', direction: 'asc', search: '', favoritesOnly: false};
    let groupsState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'name', direction: 'asc', search: '', favoritesOnly: false};
    let auditRequestId = 0;
    let databaseOverviewRequestId = 0;
    let memoryOverviewRequestId = 0;
    let segmentsRequestId = 0;
    let auditActionsLoaded = false;
    let auditUsersLoaded = false;
    let auditState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'created', direction: 'desc'};
    const activePageStorageKey = 'gp_active_page';
    const activeConnectionStorageKey = 'gp_active_connection';
    const sidebarCollapsedStorageKey = 'gp_sidebar_collapsed';
    const sidebarSectionsCollapsedStorageKey = 'gp_sidebar_sections_collapsed';
    const tableChartCollapsedStorageKey = 'gp_table_chart_collapsed';
    const connectionApiUrl = '/connections/';
    const connectionTestApiUrl = '/connections/test/';
    const connectionDeleteApiUrl = '/connections/delete/';
    const segmentsInfoApiUrl = '/segments/info/';
    const databaseOverviewApiUrl = '/databases/overview/';
    const databaseSchemasApiUrl = '/databases/schemas/';
    const tableSizesApiUrl = '/tables/sizes/';
    const viewsListApiUrl = '/views/list/';
    const functionsListApiUrl = '/functions/list/';
    const usersListApiUrl = '/users/list/';
    const groupsListApiUrl = '/groups/list/';
    const tempTablesApiUrl = '/temp-tables/sizes/';
    const toastTablesApiUrl = '/toast-tables/sizes/';
    const tempTablesState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: ''};
    const tempTablesPager = new PagedTable({
        state: tempTablesState,
        apiUrl: tempTablesApiUrl,
        ids: {body: 'tempTablesTableBody', count: 'tempTablesCount', info: 'tempTablePaginationInfo', prev: 'tempTablePrevPageBtn', next: 'tempTableNextPageBtn', search: 'tempTableSearchInput'},
        sortAttr: 'data-temp-table-sort',
        colspan: 5,
        itemsKey: 'temp_tables',
        countLabel: 'временных таблиц',
        emptyMessage: 'Временные таблицы не найдены',
        loadingMessage: 'Загрузка временных таблиц...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки временных таблиц',
        errorFallbackMessage: 'Не удалось получить временные таблицы',
        defaultDirection: sort => (sort === 'size_bytes' ? 'desc' : 'asc'),
        renderRow: table => `
            <tr>
                <td>${escapeHtml(table.schema_name || '-')}</td>
                <td><strong>${escapeHtml(table.table_name || '-')}</strong></td>
                <td>${escapeHtml(table.table_owner || '-')}</td>
                <td>${escapeHtml(table.table_size || '-')}</td>
                <td class="backend-terminate-actions">
                    ${canRunDestructiveActions() ? `<button type="button" class="btn btn-sm btn-outline-danger temp-table-delete-btn" data-temp-table-schema="${escapeHtml(table.schema_name)}" data-temp-table-name="${escapeHtml(table.table_name)}" title="Удалить временную таблицу ${escapeHtml(table.schema_name)}.${escapeHtml(table.table_name)}" aria-label="Удалить временную таблицу ${escapeHtml(table.schema_name)}.${escapeHtml(table.table_name)}"><i class="fas fa-trash"></i> Удалить</button>` : '—'}
                </td>
            </tr>
        `,
        renderSummary(data) {
            updateTempTableDistributionChart(data ? (data.temp_table_distribution || data.temp_tables || []) : []);
        }
    });
    const toastTablesState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0, sort: 'toast_total_bytes', direction: 'desc', search: '', favoritesOnly: false};
    const toastTablesPager = new PagedTable({
        state: toastTablesState,
        apiUrl: toastTablesApiUrl,
        ids: {body: 'toastTablesTableBody', count: 'toastTablesCount', info: 'toastTablePaginationInfo', prev: 'toastTablePrevPageBtn', next: 'toastTableNextPageBtn', search: 'toastTableSearchInput', favoritesFilter: 'toastTableFavoritesFilter'},
        sortAttr: 'data-toast-table-sort',
        colspan: 8,
        itemsKey: 'toast_tables',
        countLabel: 'TOAST-таблиц',
        emptyMessage: 'TOAST-таблицы с данными не найдены',
        loadingMessage: 'Загрузка TOAST-таблиц...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки TOAST-таблиц',
        errorFallbackMessage: 'Не удалось получить TOAST-таблицы',
        defaultDirection: sort => (['schema_name', 'table_name', 'toast_table_name'].includes(sort) ? 'asc' : 'desc'),
        renderRow: table => {
            const share = Number(table.toast_share) || 0;
            const shareBadge = share >= 50 ? ' <span class="badge bg-warning text-dark">&gt;50%</span>' : '';
            const toastDetails = `${formatDatabaseSize(table.toast_bytes).value} ${formatDatabaseSize(table.toast_bytes).unit} + ${formatDatabaseSize(table.toast_index_bytes).value} ${formatDatabaseSize(table.toast_index_bytes).unit}`;
            return `
            <tr>
                <td class="favorite-column">${favoriteButton('table', `${table.schema_name}\u001f${table.table_name}`, `${table.schema_name}.${table.table_name}`)}</td>
                <td>${escapeHtml(table.schema_name || '-')}</td>
                <td><strong>${escapeHtml(table.table_name || '-')}</strong></td>
                <td><code>${escapeHtml(table.toast_table_name || '-')}</code></td>
                <td title="${escapeHtml(toastDetails)}">${escapeHtml(table.toast_total_size || '-')}</td>
                <td>${escapeHtml(table.heap_size || '-')}</td>
                <td>${share.toFixed(1)}%${shareBadge}</td>
                <td>${Number(table.dead_chunks || 0).toLocaleString()}</td>
            </tr>`;
        },
        renderSummary(data) {
            const total = document.getElementById('toastTablesTotalSize');
            if (total) total.textContent = data && toastTablesState.totalCount ? `${translateInterfaceText('Всего')}: ${data.all_toast_size || '-'}` : '';
        }
    });
    const schemaSizesPager = new PagedTable({
        state: schemaSizesState,
        apiUrl: databaseSchemasApiUrl,
        ids: {body: 'schemaSizesTableBody', count: 'schemaSizesCount', info: 'schemaPaginationInfo', prev: 'schemaPrevPageBtn', next: 'schemaNextPageBtn', search: 'schemaSearchInput', favoritesFilter: 'schemaFavoritesFilter'},
        sortAttr: 'data-schema-sort',
        colspan: 5,
        itemsKey: 'schemas',
        countLabel: 'схем',
        emptyMessage: 'Схемы не найдены',
        loadingMessage: 'Загрузка размеров схем...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки размеров схем',
        errorFallbackMessage: 'Не удалось получить размеры схем',
        defaultDirection: sort => (sort === 'size_bytes' ? 'desc' : 'asc'),
        renderRow: schema => `
            <tr>
                <td class="favorite-column">${favoriteButton('schema', schema.schema_name, schema.schema_name)}</td>
                <td><strong>${escapeHtml(schema.schema_name || '-')}</strong></td>
                <td>${escapeHtml(schema.schema_owner || '-')}</td>
                <td>${escapeHtml(schema.table_count ?? 0)}</td>
                <td>${escapeHtml(schema.table_size || formatDatabaseSize(schema.size_bytes).value + ' ' + formatDatabaseSize(schema.size_bytes).unit)}</td>
            </tr>
        `,
        renderSummary(data) {
            updateSchemaDistributionChart(data ? (data.schema_distribution || data.schemas || []) : []);
        }
    });
    const tableSizesPager = new PagedTable({
        state: tableSizesState,
        apiUrl: tableSizesApiUrl,
        ids: {body: 'tableSizesTableBody', count: 'tableSizesCount', info: 'tablePaginationInfo', prev: 'tablePrevPageBtn', next: 'tableNextPageBtn', search: 'tableSearchInput', favoritesFilter: 'tableFavoritesFilter'},
        sortAttr: 'data-table-sort',
        colspan: 8,
        itemsKey: 'tables',
        countLabel: 'таблиц',
        emptyMessage: 'Таблицы не найдены',
        loadingMessage: 'Загрузка размеров таблиц...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки размеров таблиц',
        errorFallbackMessage: 'Не удалось получить размеры таблиц',
        defaultDirection: sort => (['size_bytes', 'index_size_bytes', 'index_count', 'row_count'].includes(sort) ? 'desc' : 'asc'),
        renderRow: table => `
            <tr>
                <td class="favorite-column">${favoriteButton('table', `${table.schema_name}\u001f${table.table_name}`, `${table.schema_name}.${table.table_name}`)}</td>
                <td>${escapeHtml(table.schema_name || '-')}</td>
                <td><strong>${escapeHtml(table.table_name || '-')}</strong></td>
                <td>${escapeHtml(table.table_owner || '-')}</td>
                <td>${escapeHtml(table.table_size || '-')}</td>
                <td>${escapeHtml(table.index_size || '-')}</td>
                <td>${formatRowCount(table.index_count)}</td>
                <td>${formatRowCount(table.row_count)}</td>
            </tr>
        `,
        renderSummary(data) {
            updateTableDistributionChart(data ? (data.table_distribution || data.tables || []) : []);
        }
    });
    const viewsPager = new PagedTable({
        state: viewsState,
        apiUrl: viewsListApiUrl,
        ids: {body: 'viewsTableBody', count: 'viewsCount', info: 'viewPaginationInfo', prev: 'viewPrevPageBtn', next: 'viewNextPageBtn', search: 'viewSearchInput', favoritesFilter: 'viewFavoritesFilter'},
        filters: [{id: 'viewTypeFilter', stateKey: 'viewType', param: 'view_type'}],
        sortAttr: 'data-view-sort',
        colspan: 8,
        itemsKey: 'views',
        countLabel: 'представлений',
        emptyMessage: 'Представления не найдены',
        loadingMessage: 'Загрузка представлений...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки представлений',
        errorFallbackMessage: 'Не удалось получить представления',
        defaultDirection: sort => (['size_bytes', 'index_size_bytes', 'row_count'].includes(sort) ? 'desc' : 'asc'),
        renderRow: view => `
            <tr>
                <td class="favorite-column">${favoriteButton('view', `${view.schema_name}\u001f${view.view_name}`, `${view.schema_name}.${view.view_name}`)}</td>
                <td>${escapeHtml(view.schema_name || '-')}</td>
                <td><strong>${escapeHtml(view.view_name || '-')}</strong></td>
                <td>${escapeHtml(view.view_owner || '-')}</td>
                <td>${escapeHtml(view.view_type || '-')}</td>
                <td>${escapeHtml(view.view_size || '-')}</td>
                <td>${escapeHtml(view.index_size || '-')}</td>
                <td>${formatRowCount(view.row_count)}</td>
            </tr>
        `,
        renderSummary(data) {
            updateViewsSummaryChart(data ? (data.summary || null) : null, data ? (data.views || []) : []);
        }
    });
    const functionsPager = new PagedTable({
        state: functionsState,
        apiUrl: functionsListApiUrl,
        ids: {body: 'functionsTableBody', count: 'functionsCount', info: 'functionPaginationInfo', prev: 'functionPrevPageBtn', next: 'functionNextPageBtn', search: 'functionSearchInput', favoritesFilter: 'functionFavoritesFilter'},
        sortAttr: 'data-function-sort',
        colspan: 5,
        itemsKey: 'functions',
        countLabel: 'функций',
        emptyMessage: 'Функции не найдены',
        loadingMessage: 'Загрузка функций...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки функций',
        errorFallbackMessage: 'Не удалось получить функции',
        defaultDirection: () => 'asc',
        renderRow: item => `<tr>
                <td class="favorite-column">${favoriteButton('function', `${item.schema_name}\u001f${item.function_name}\u001f${item.arguments || ''}`, `${item.schema_name}.${item.function_name}(${item.arguments || ''})`)}</td>
                <td>${escapeHtml(item.schema_name || '—')}</td>
                <td><strong>${escapeHtml(item.function_name || '—')}</strong></td>
                <td><code>${escapeHtml(item.return_type || '—')}</code></td>
                <td><code>${escapeHtml(item.arguments || '—')}</code></td>
            </tr>`
    });
    const usersPager = new PagedTable({
        state: usersState,
        apiUrl: usersListApiUrl,
        ids: {body: 'usersTableBody', count: 'usersCount', info: 'usersPaginationInfo', prev: 'usersPrevPageBtn', next: 'usersNextPageBtn', search: 'usersSearchInput', favoritesFilter: 'usersFavoritesFilter'},
        sortAttr: 'data-users-sort',
        colspan: 9,
        itemsKey: 'roles',
        countLabel: 'пользователей',
        emptyMessage: 'Пользователи не найдены',
        loadingMessage: 'Загрузка пользователей...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки пользователей',
        errorFallbackMessage: 'Не удалось получить список пользователей',
        defaultDirection: sort => (['connection_limit', 'valid_until'].includes(sort) ? 'desc' : 'asc'),
        renderRow: role => renderRoleRow(role, false),
        renderSummary(data) {
            if (data) updateUsersPrivilegeCharts(data.roles || [], data.summary || null);
            else updateUsersPrivilegeCharts([]);
        }
    });
    const groupsPager = new PagedTable({
        state: groupsState,
        apiUrl: groupsListApiUrl,
        ids: {body: 'groupsTableBody', count: 'groupsCount', info: 'groupsPaginationInfo', prev: 'groupsPrevPageBtn', next: 'groupsNextPageBtn', search: 'groupsSearchInput', favoritesFilter: 'groupsFavoritesFilter'},
        sortAttr: 'data-groups-sort',
        colspan: 10,
        itemsKey: 'roles',
        formatCount: items => `${items.length} записей`,
        emptyMessage: 'Группы не найдены',
        loadingMessage: 'Загрузка групп...',
        notConnectedMessage: 'Выберите сохранённое подключение для загрузки групп',
        errorFallbackMessage: 'Не удалось получить список групп',
        defaultDirection: sort => (['connection_limit', 'valid_until', 'member_count'].includes(sort) ? 'desc' : 'asc'),
        renderRow: role => renderRoleRow(role, true),
        renderSummary(data) {
            if (data) updateGroupsPrivilegeCharts(data.roles || [], data.summary || null);
            else updateGroupsPrivilegeCharts([]);
        }
    });
    // Серверный statement_timeout (15 с) короче этого лимита, поэтому обычно сервер
    // сам сообщает причину раньше, чем сработает клиентский таймаут.
    const CONNECTION_REQUEST_TIMEOUT_MS = 20000;
    const deleteTempTableApiUrl = '/temp-tables/delete/';
    const databasePdfReportApiUrl = '/reports/database.pdf';
    const distributionTablesApiUrl = '/distribution/tables/';
    const distributionInfoApiUrl = '/distribution/info/';
    const activeQueriesApiUrl = '/queries/active/';
    const terminateActiveQueryApiUrl = '/queries/terminate/';
    const activeSessionsApiUrl = '/sessions/active/';
    const terminateActiveSessionApiUrl = '/sessions/terminate/';
    const blockingLocksApiUrl = '/locks/blocking/';
    const terminateLockProcessApiUrl = '/locks/terminate/';
    const idleTransactionsApiUrl = '/transactions/idle/';
    const terminateIdleTransactionApiUrl = '/transactions/terminate/';
    const memoryOverviewApiUrl = '/memory/overview/';
    const maintenanceStatsApiUrl = '/maintenance/stats/';
    const maintenanceOperationApiUrl = '/maintenance/operation/';
    const maintenanceJobsApiUrl = '/maintenance/jobs/';
    const auditEventsApiUrl = '/audit/events/';
    const sidebarSettingsApiUrl = '/settings/sidebar/';
    const languageSettingsApiUrl = '/settings/language/';
    const paginationSettingsApiUrl = '/settings/pagination/';
    const activeSettingsTabStorageKey = 'db_stat_settings_tab';
    const favoritesApiUrl = '/favorites/';
    let favoriteKeys = new Set();
    let favoriteItems = [];
    let favoritesState = {page: 1, pageSize: defaultPaginationPageSize, totalCount: 0};
    let favoritesSortState = {column: 'object', direction: 'asc'};

    const pageTitles = {
        'home': 'Главная <small>Описание разделов</small>',
        'database-overview': 'База данных <small>Размеры и структура</small>',
        'segments': 'Сегменты <small>Состояние и конфигурация</small>',
        'databases': 'Схемы <small>Список схем</small>',
        'tables': 'Таблицы <small>Список таблиц</small>',
        'views': 'Представления <small>Список представлений</small>',
        'functions': 'Функции <small>Список функций</small>',
        'distribution': 'Распределение <small>Перекос данных</small>',
        'temp-tables': 'Временные таблицы <small>Активные временные таблицы</small>',
        'toast-tables': 'TOAST-таблицы <small>Вынесенные большие значения</small>',
        'queries': 'Активные запросы <small>Долгие запросы</small>',
        'sessions': 'Сессии <small>Пользователи и подключения</small>',
        'locks': 'Блокировки <small>Кто кого блокирует</small>',
        'transactions': 'Транзакции <small>Commit / Rollback</small>',
        'memory': 'Память <small>Параметры памяти</small>',
        'users': 'Пользователи <small>Список пользователей</small>',
        'groups': 'Группы <small>Список групп</small>',
        'maintenance': 'Обслуживание <small>Очистка / анализ</small>',
        'audit': 'Аудит <small>Действия пользователя</small>',
        'favorites': 'Избранные объекты <small>Сохранённые объекты подключения</small>',
        'settings': 'Настройки <small>Интерфейс и меню</small>'
    };


    const greenplumOnlyPages = new Set(['segments', 'distribution']);

    function isGreenplumCompatibleConnection(conn) {
        return new Set(['greenplum', 'greengage']).has(String(conn?.db_type || '').toLowerCase());
    }

    function isSidebarPageEnabled(pageId) {
        if (!pageId || pageId === 'home' || pageId === 'favorites' || pageId === 'settings') return true;
        return getVisibleSidebarPages().includes(pageId);
    }

    function isPageAvailableForConnection(pageId, conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        if (!isSidebarPageEnabled(pageId)) return false;
        if (pageId === 'home' || pageId === 'audit' || pageId === 'settings') return true;
        if (pageId === 'favorites') return Boolean(conn);
        if (!pageId || !conn) return false;
        if (!isGreenplumCompatibleConnection(conn) && greenplumOnlyPages.has(pageId)) return false;
        return true;
    }

    function getDefaultPageForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        if (!conn) return 'home';
        const preferredPages = isGreenplumCompatibleConnection(conn)
            ? ['segments', 'database-overview', 'databases', 'tables', 'views', 'functions', 'temp-tables', 'toast-tables', 'distribution', 'queries', 'sessions', 'locks', 'transactions', 'memory', 'users', 'groups', 'maintenance', 'audit']
            : ['database-overview', 'databases', 'tables', 'views', 'functions', 'temp-tables', 'toast-tables', 'queries', 'sessions', 'locks', 'transactions', 'memory', 'users', 'groups', 'maintenance', 'audit'];
        return preferredPages.find(page => isPageAvailableForConnection(page, conn)) || 'home';
    }

    function updateSidebarForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        document.querySelectorAll('.nav-item[data-page]').forEach(item => {
            const isAvailable = isPageAvailableForConnection(item.dataset.page, conn);
            item.classList.toggle('d-none', !isAvailable);
            item.setAttribute('aria-hidden', String(!isAvailable));
            item.tabIndex = isAvailable ? 0 : -1;
        });

        document.querySelectorAll('.nav-section').forEach(section => {
            const visibleItems = Array.from(section.querySelectorAll('.nav-item')).filter(item => !item.classList.contains('d-none'));
            section.classList.toggle('d-none', visibleItems.length === 0);
        });
    }

    const currentDbUserElement = document.getElementById('dbUserData');
    const currentDbUser = currentDbUserElement ? JSON.parse(currentDbUserElement.textContent || 'null') : null;
    const dismissedBackgroundJobsStorageKey = `db_stat_dismissed_background_jobs_${currentDbUser?.id || 'anonymous'}`;
    const dismissedBackgroundJobIds = new Set((localStorage.getItem(dismissedBackgroundJobsStorageKey) || '').split(',').filter(Boolean));
    let latestBackgroundJobs = [];

    function canManageConnections() {
        return currentDbUser?.can_manage_connections === true;
    }

    function canRunDestructiveActions() {
        return currentDbUser?.can_run_destructive_actions === true;
    }

    function canEditConnection(conn) {
        return canManageConnections() && conn?.created_by_id != null && String(conn.created_by_id) === String(currentDbUser?.id);
    }

    function canDeleteConnection(conn) {
        return canEditConnection(conn);
    }

    function getConnectionDbTypeIconSrc(dbType, iconElement) {
        const normalizedType = String(dbType || '').toLowerCase();
        const iconsByType = {
            greenplum: iconElement?.dataset?.greenplumIcon,
            greengage: iconElement?.dataset?.greengageIcon,
            postgresql: iconElement?.dataset?.postgresqlIcon
        };
        return iconsByType[normalizedType] || iconsByType.postgresql;
    }

    function updateConnectionActionButtons(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const editButton = document.getElementById('connectionEditBtn');
        const reportButton = document.getElementById('databasePdfReportBtn');
        if (editButton) {
            editButton.classList.toggle('d-none', !canEditConnection(conn));
        }
        if (reportButton) reportButton.disabled = !conn;
    }

    function updateSortHeaderState(button, isActive, direction) {
        // Keeps aria-sort on the <th> in sync with the icon swap every sort
        // indicator function already does, so screen readers see the same
        // sort state sighted users see from the icon.
        const header = button.closest('th');
        if (header) header.setAttribute('aria-sort', isActive ? (direction === 'asc' ? 'ascending' : 'descending') : 'none');
        const icon = button.querySelector('i');
        if (icon) icon.className = isActive ? `fas fa-sort-${direction === 'asc' ? 'up' : 'down'}` : 'fas fa-sort';
    }

    function updatePaginationButtons(state, prevButtonId, nextButtonId, page = state.page) {
        const totalPages = Math.max(Math.ceil(state.totalCount / state.pageSize), 1);
        const prev = document.getElementById(prevButtonId);
        const next = document.getElementById(nextButtonId);
        if (prev) prev.disabled = page <= 1;
        if (next) next.disabled = page >= totalPages;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function favoriteId(type, key) { return `${type}:${key}`; }

    function backendTerminationKey(connectionId, pid) { return `${connectionId}:${pid}`; }

    function favoriteButton(type, key, label) {
        const selected = favoriteKeys.has(favoriteId(type, key));
        const action = translateInterfaceText(selected ? 'Удалить из избранного' : 'Добавить в избранное');
        return `<button type="button" class="favorite-btn${selected ? ' active' : ''}" data-favorite-type="${escapeHtml(type)}" data-favorite-key="${escapeHtml(key)}" data-favorite-label="${escapeHtml(label)}" title="${action}: ${escapeHtml(label)}" aria-label="${action}: ${escapeHtml(label)}" aria-pressed="${selected}"><i class="${selected ? 'fas' : 'far'} fa-star"></i></button>`;
    }

    function updateFavoriteButtons() {
        document.querySelectorAll('[data-favorite-type][data-favorite-key]').forEach(button => {
            const selected = favoriteKeys.has(favoriteId(button.dataset.favoriteType, button.dataset.favoriteKey));
            const action = translateInterfaceText(selected ? 'Удалить из избранного' : 'Добавить в избранное');
            const label = button.dataset.favoriteLabel || button.dataset.favoriteKey;
            button.classList.toggle('active', selected);
            button.setAttribute('aria-pressed', String(selected));
            button.title = `${action}: ${label}`;
            button.setAttribute('aria-label', `${action}: ${label}`);
            button.querySelector('i').className = `${selected ? 'fas' : 'far'} fa-star`;
        });
    }

    function setFavoriteButtonsDisabled(type, key, disabled) {
        document.querySelectorAll('[data-favorite-type][data-favorite-key]').forEach(button => {
            if (button.dataset.favoriteType === type && button.dataset.favoriteKey === key) {
                button.disabled = disabled;
            }
        });
    }

    function applyFavoriteChange(data) {
        const id = favoriteId(data.object_type, data.object_key);
        if (data.is_favorite) {
            favoriteKeys.add(id);
            if (!favoriteItems.some(item => favoriteId(item.object_type, item.object_key) === id)) {
                favoriteItems.push({object_type: data.object_type, object_key: data.object_key});
            }
        } else {
            favoriteKeys.delete(id);
            favoriteItems = favoriteItems.filter(item => favoriteId(item.object_type, item.object_key) !== id);
        }
        updateFavoriteButtons();
        if (document.getElementById('page-favorites')?.classList.contains('active')) {
            renderFavoritesPage();
        }
    }

    function refreshFavoriteFilteredTable(objectType) {
        const targets = {
            schema: {page: 'databases', state: schemaSizesState, refresh: refreshSchemaSizesForConnection},
            table: {page: 'tables', state: tableSizesState, refresh: refreshTableSizesForConnection},
            view: {page: 'views', state: viewsState, refresh: refreshViewsForConnection},
            function: {page: 'functions', state: functionsState, refresh: refreshFunctionsForConnection},
            user: {page: 'users', state: usersState, refresh: refreshUsersForConnection},
            group: {page: 'groups', state: groupsState, refresh: refreshGroupsForConnection}
        };
        const target = targets[objectType];
        if (target?.state.favoritesOnly && document.getElementById(`page-${target.page}`)?.classList.contains('active')) {
            target.refresh();
        }
        if (objectType === 'table' && toastTablesState.favoritesOnly && document.getElementById('page-toast-tables')?.classList.contains('active')) {
            refreshToastTablesForConnection();
        }
    }

    function loadFavorites(connectionId = activeConnectionId) {
        favoritesState.page = 1;
        if (!connectionId) {
            favoriteItems = [];
            favoriteKeys = new Set();
            renderFavoritesPage();
            return Promise.resolve();
        }
        return fetch(`${favoritesApiUrl}?id=${encodeURIComponent(connectionId)}`)
            .then(response => response.ok ? response.json() : Promise.reject(new Error('Не удалось загрузить избранное')))
            .then(data => {
                if (String(connectionId) !== String(activeConnectionId)) return;
                favoriteItems = data.favorites || [];
                favoriteKeys = new Set(favoriteItems.map(item => favoriteId(item.object_type, item.object_key)));
                updateFavoriteButtons();
                renderFavoritesPage();
            });
    }

    function renderFavoritesPage() {
        const tbody = document.getElementById('favoritesObjectsTableBody');
        const count = document.getElementById('favoritesObjectsCount');
        favoritesState.totalCount = favoriteItems.length;
        const totalPages = Math.max(Math.ceil(favoritesState.totalCount / favoritesState.pageSize), 1);
        favoritesState.page = Math.min(favoritesState.page, totalPages);
        if (count) count.textContent = activeConnectionId ? `${favoriteItems.length} объектов` : 'Нет данных';
        const paginationInfo = document.getElementById('favoritesPaginationInfo');
        if (paginationInfo) paginationInfo.textContent = `Страница ${favoritesState.page} из ${totalPages}`;
        const previousButton = document.getElementById('favoritesPrevPageBtn');
        const nextButton = document.getElementById('favoritesNextPageBtn');
        if (previousButton) previousButton.disabled = favoritesState.page <= 1;
        if (nextButton) nextButton.disabled = favoritesState.page >= totalPages;
        if (!tbody) return;
        if (!activeConnectionId) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-muted">Выберите подключение для просмотра избранных объектов</td></tr>';
            return;
        }
        if (!favoriteItems.length) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-muted">Для выбранного подключения нет избранных объектов</td></tr>';
            return;
        }
        const typeLabels = {schema: 'Схема', table: 'Таблица', view: 'Представление', function: 'Функция', user: 'Пользователь', group: 'Группа'};
        const sortedItems = [...favoriteItems].sort((first, second) => {
            const value = item => favoritesSortState.column === 'type'
                ? (typeLabels[item.object_type] || item.object_type)
                : String(item.object_key || '').split('\u001f').join('.');
            const comparison = String(value(first)).localeCompare(String(value(second)), 'ru', {numeric: true, sensitivity: 'base'});
            if (comparison !== 0) return favoritesSortState.direction === 'asc' ? comparison : -comparison;
            return favoriteId(first.object_type, first.object_key).localeCompare(favoriteId(second.object_type, second.object_key), 'ru', {numeric: true, sensitivity: 'base'});
        });
        updateFavoritesSortIndicators();
        const offset = (favoritesState.page - 1) * favoritesState.pageSize;
        tbody.innerHTML = sortedItems.slice(offset, offset + favoritesState.pageSize).map(item => {
            const keyParts = String(item.object_key || '').split('\u001f');
            const label = item.object_type === 'function'
                ? `${keyParts[0] || ''}.${keyParts[1] || ''}(${keyParts[2] || ''})`
                : keyParts.join('.');
            const targetAttributes = `data-favorite-target-type="${escapeHtml(item.object_type)}" data-favorite-target-key="${escapeHtml(item.object_key)}"`;
            return `<tr><td class="favorite-column">${favoriteButton(item.object_type, item.object_key, label)}</td><td><button type="button" class="favorite-object-link" ${targetAttributes}>${escapeHtml(typeLabels[item.object_type] || item.object_type)}</button></td><td><button type="button" class="favorite-object-link" ${targetAttributes}>${escapeHtml(label)}</button></td></tr>`;
        }).join('');
    }

    function updateFavoritesSortIndicators() {
        document.querySelectorAll('[data-favorites-sort]').forEach(button => {
            const isActive = button.dataset.favoritesSort === favoritesSortState.column;
            button.classList.toggle('active', isActive);
            updateSortHeaderState(button, isActive, favoritesSortState.direction);
        });
    }

    function openFavoriteObject(objectType, objectKey) {
        const targets = {
            schema: {page: 'databases', state: schemaSizesState, input: 'schemaSearchInput', filter: 'schemaFavoritesFilter'},
            table: {page: 'tables', state: tableSizesState, input: 'tableSearchInput', filter: 'tableFavoritesFilter'},
            view: {page: 'views', state: viewsState, input: 'viewSearchInput', filter: 'viewFavoritesFilter'},
            function: {page: 'functions', state: functionsState, input: 'functionSearchInput', filter: 'functionFavoritesFilter'},
            user: {page: 'users', state: usersState, input: 'usersSearchInput', filter: 'usersFavoritesFilter'},
            group: {page: 'groups', state: groupsState, input: 'groupsSearchInput', filter: 'groupsFavoritesFilter'}
        };
        const target = targets[objectType];
        if (!target) return;
        const keyParts = String(objectKey || '').split('\u001f');
        const search = objectType === 'schema'
            ? keyParts[0]
            : (objectType === 'function' ? keyParts[1] : keyParts[keyParts.length - 1]);
        target.state.search = search;
        target.state.favoritesOnly = true;
        if ('page' in target.state) target.state.page = 1;
        const searchInput = document.getElementById(target.input);
        const favoritesFilter = document.getElementById(target.filter);
        if (searchInput) searchInput.value = search;
        if (favoritesFilter) favoritesFilter.value = 'favorites';
        activatePage(target.page);
    }

    function initFavoriteControls() {
        document.getElementById('favoritesPrevPageBtn')?.addEventListener('click', () => {
            if (favoritesState.page > 1) {
                favoritesState.page -= 1;
                renderFavoritesPage();
            }
        });
        document.getElementById('favoritesNextPageBtn')?.addEventListener('click', () => {
            if (favoritesState.page * favoritesState.pageSize < favoritesState.totalCount) {
                favoritesState.page += 1;
                renderFavoritesPage();
            }
        });
        document.querySelectorAll('[data-favorites-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const column = this.dataset.favoritesSort;
                if (favoritesSortState.column === column) {
                    favoritesSortState.direction = favoritesSortState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    favoritesSortState = {column, direction: 'asc'};
                }
                renderFavoritesPage();
            });
        });
        updateFavoritesSortIndicators();
        document.addEventListener('click', event => {
            const objectLink = event.target.closest('[data-favorite-target-type][data-favorite-target-key]');
            if (objectLink) {
                openFavoriteObject(objectLink.dataset.favoriteTargetType, objectLink.dataset.favoriteTargetKey);
                return;
            }
            const button = event.target.closest('[data-favorite-type][data-favorite-key]');
            if (!button || !activeConnectionId) return;
            const connectionId = activeConnectionId;
            const objectType = button.dataset.favoriteType;
            const objectKey = button.dataset.favoriteKey;
            setFavoriteButtonsDisabled(objectType, objectKey, true);
            connectionRequest(favoritesApiUrl, {id: connectionId, object_type: objectType, object_key: objectKey})
                .then(data => {
                    if (String(connectionId) !== String(activeConnectionId)) return;
                    applyFavoriteChange(data);
                    refreshFavoriteFilteredTable(data.object_type);
                })
                .catch(error => showToast(`❌ ${error.message || 'Не удалось изменить избранное'}`))
                .finally(() => setFavoriteButtonsDisabled(objectType, objectKey, false));
        });
    }

    // ============================
    // INIT
    // ============================
    function initFilterSelects() {
        const closeAll = except => {
            document.querySelectorAll('.filter-select-box.is-open').forEach(box => {
                if (box === except) return;
                box.classList.remove('is-open');
                box.querySelector('.filter-select__toggle')?.setAttribute('aria-expanded', 'false');
            });
        };

        document.querySelectorAll('.filter-select-box select').forEach(select => {
            if (select.dataset.customized === 'true') return;
            select.dataset.customized = 'true';
            select.classList.add('visually-hidden');

            const custom = document.createElement('div');
            custom.className = 'filter-select';
            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'filter-select__toggle';
            toggle.setAttribute('aria-haspopup', 'listbox');
            toggle.setAttribute('aria-expanded', 'false');
            toggle.setAttribute('aria-label', select.getAttribute('aria-label') || 'Фильтр');
            const menu = document.createElement('div');
            menu.className = 'filter-select__menu';
            menu.setAttribute('role', 'listbox');
            custom.append(toggle, menu);
            select.insertAdjacentElement('afterend', custom);

            const render = () => {
                const options = Array.from(select.options);
                const selectedIndex = Math.max(select.selectedIndex, 0);
                toggle.innerHTML = `<span>${escapeHtml(options[selectedIndex]?.textContent || '')}</span><i class="fas fa-chevron-down" aria-hidden="true"></i>`;
                menu.innerHTML = '';
                options.forEach((option, index) => {
                    const item = document.createElement('button');
                    item.type = 'button';
                    item.className = `filter-select__option${index === selectedIndex ? ' is-selected' : ''}`;
                    item.setAttribute('role', 'option');
                    item.setAttribute('aria-selected', String(index === selectedIndex));
                    item.innerHTML = `<i class="far fa-check-circle" aria-hidden="true"></i><span>${escapeHtml(option.textContent)}</span>`;
                    item.addEventListener('click', () => {
                        if (select.selectedIndex !== index) {
                            select.selectedIndex = index;
                            select.dispatchEvent(new Event('change', {bubbles: true}));
                        }
                        render();
                        closeAll();
                        toggle.focus();
                    });
                    menu.appendChild(item);
                });
            };

            toggle.addEventListener('click', event => {
                event.stopPropagation();
                const opening = !select.closest('.filter-select-box').classList.contains('is-open');
                closeAll();
                select.closest('.filter-select-box').classList.toggle('is-open', opening);
                toggle.setAttribute('aria-expanded', String(opening));
                if (opening) menu.querySelector('.is-selected')?.focus();
            });
            custom.addEventListener('keydown', event => {
                const items = Array.from(menu.querySelectorAll('.filter-select__option'));
                const index = items.indexOf(document.activeElement);
                if (event.key === 'Escape') {
                    closeAll();
                    toggle.focus();
                } else if (event.key === 'ArrowDown' && items.length) {
                    event.preventDefault();
                    items[(index + 1) % items.length].focus();
                } else if (event.key === 'ArrowUp' && items.length) {
                    event.preventDefault();
                    items[(index - 1 + items.length) % items.length].focus();
                }
            });
            select.addEventListener('change', render);
            new MutationObserver(render).observe(select, {childList: true, subtree: true});
            render();
        });
        document.addEventListener('click', () => closeAll());
    }

    document.addEventListener('DOMContentLoaded', function () {
        initSettingsTabs();
        initReportsSettings();
        initThemeSettings();
        initPaginationPageSizeControls();
        initPaginationSettingsEditor();
        applySidebarSectionOrder(currentDbUser?.sidebar_section_order);
        applySidebarPageOrder(getVisibleSidebarPages());
        loadConnections();
        initConnectionSelect();
        initConnectionInfoTooltip();
        initCharts();
        initConnectionActionButtons();
        initDatabasePdfReport();
        initNavigation();
        initSidebarCollapse();
        initSidebarSectionToggles();
        initBrandHomeNavigation();
        initTableChartToggles();
        activatePage(getStoredActivePage() || getCurrentActivePageId(), {persist: false});
        initSegmentsTableSorting();
        initSchemaSizesControls();
        initTableSizesControls();
        initViewsControls();
        initFunctionsControls();
        initTempTablesControls();
        initToastTablesControls();
        initDistributionControls();
        initActiveQueriesControls();
        initActiveSessionsControls();
        initBlockingLocksControls();
        initIdleTransactionsControls();
        initMaintenanceStatsControls();
        initBackgroundJobs();
        initUsersControls();
        initGroupsControls();
        initFavoriteControls();
        initAuditControls();
        initSidebarSettings();
        initLanguageSettings();
        initFilterSelects();
        initLogoutForm();
        initSessionCountdown();
        modalInstance = new bootstrap.Modal(document.getElementById('connectionModal'));
        initConnectionDbTypeSelect();
        updateConnectionDbTypeIcon();

        document.getElementById('menuToggle').addEventListener('click', function () {
            document.body.classList.remove('sidebar-collapsed');
            updateSidebarLogoToggle(false);
            document.getElementById('sidebar').classList.toggle('open');
        });

        // Close sidebar on outside click for mobile
        document.addEventListener('click', function (e) {
            const sidebar = document.getElementById('sidebar');
            const toggle = document.getElementById('menuToggle');
            if (window.innerWidth <= 992) {
                if (sidebar.classList.contains('open') &&
                    !sidebar.contains(e.target) &&
                    !toggle.contains(e.target)) {
                    sidebar.classList.remove('open');
                }
            }
        });
    });




    function getCollapsedTableCharts() {
        try {
            return JSON.parse(localStorage.getItem(tableChartCollapsedStorageKey) || '{}') || {};
        } catch (error) {
            return {};
        }
    }

    function setTableChartCollapsed(toggle, isCollapsed, {persist = true} = {}) {
        const targetId = toggle?.dataset?.chartToggle;
        const chart = targetId ? document.getElementById(targetId) : null;
        if (!toggle || !chart) return;

        chart.classList.toggle('table-chart-collapsed', isCollapsed);
        toggle.setAttribute('aria-expanded', String(!isCollapsed));
        toggle.setAttribute('title', isCollapsed ? 'Развернуть график' : 'Свернуть график');
        toggle.setAttribute('aria-label', isCollapsed ? 'Развернуть график' : 'Свернуть график');

        const icon = toggle.querySelector('i');
        if (icon) {
            icon.classList.toggle('fa-chevron-up', !isCollapsed);
            icon.classList.toggle('fa-chevron-down', isCollapsed);
        }
        const label = toggle.querySelector('span');
        if (label) label.textContent = isCollapsed ? 'Развернуть график' : 'Свернуть график';

        if (persist) {
            const collapsedCharts = getCollapsedTableCharts();
            collapsedCharts[targetId] = isCollapsed;
            localStorage.setItem(tableChartCollapsedStorageKey, JSON.stringify(collapsedCharts));
        }
    }

    function initTableChartToggles() {
        const collapsedCharts = getCollapsedTableCharts();
        document.querySelectorAll('[data-chart-toggle]').forEach(toggle => {
            const targetId = toggle.dataset.chartToggle;
            setTableChartCollapsed(toggle, collapsedCharts[targetId] === true, {persist: false});
            toggle.addEventListener('click', function () {
                const chart = document.getElementById(this.dataset.chartToggle);
                setTableChartCollapsed(this, !chart?.classList.contains('table-chart-collapsed'));
            });
        });
    }


    function initBrandHomeNavigation() {
        const brandHomeButton = document.getElementById('brandHomeButton');
        if (!brandHomeButton) return;
        brandHomeButton.addEventListener('click', function () {
            activatePage('home');
        });
    }

    function updateSidebarLogoToggle(isCollapsed) {
        const toggle = document.getElementById('sidebarLogoToggle');
        if (!toggle) return;
        toggle.setAttribute('aria-expanded', String(!isCollapsed));
        toggle.setAttribute('aria-label', isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар');
        toggle.setAttribute('title', isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар');
    }

    function setSidebarCollapsed(isCollapsed, {persist = true} = {}) {
        if (window.innerWidth <= 992) {
            document.body.classList.remove('sidebar-collapsed');
            updateSidebarLogoToggle(false);
            return;
        }
        document.body.classList.toggle('sidebar-collapsed', isCollapsed);
        updateSidebarLogoToggle(isCollapsed);
        if (persist) {
            localStorage.setItem(sidebarCollapsedStorageKey, isCollapsed ? '1' : '0');
        }
        setTimeout(() => {
            Object.values(charts).forEach(chart => {
                if (chart && chart.resize) chart.resize();
            });
        }, 250);
    }

    function initSidebarCollapse() {
        const toggle = document.getElementById('sidebarLogoToggle');
        const initialCollapsed = localStorage.getItem(sidebarCollapsedStorageKey) === '1';
        setSidebarCollapsed(initialCollapsed, {persist: false});
        if (toggle) {
            toggle.addEventListener('click', function () {
                setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed'));
            });
        }
        window.addEventListener('resize', function () {
            const shouldCollapse = localStorage.getItem(sidebarCollapsedStorageKey) === '1';
            setSidebarCollapsed(shouldCollapse, {persist: false});
        });
    }

    function getCollapsedSidebarSections() {
        try {
            return JSON.parse(localStorage.getItem(sidebarSectionsCollapsedStorageKey) || '{}') || {};
        } catch (error) {
            return {};
        }
    }

    function setSidebarSectionCollapsed(toggle, isCollapsed, {persist = true} = {}) {
        const section = toggle?.closest('.nav-section');
        const sectionKey = toggle?.dataset?.navSectionToggle;
        if (!toggle || !section || !sectionKey) return;

        section.classList.toggle('collapsed', isCollapsed);
        toggle.setAttribute('aria-expanded', String(!isCollapsed));
        toggle.setAttribute('title', isCollapsed ? 'Развернуть раздел' : 'Свернуть раздел');
        toggle.setAttribute('aria-label', isCollapsed ? 'Развернуть раздел' : 'Свернуть раздел');

        const icon = toggle.querySelector('i');
        if (icon) {
            icon.classList.toggle('fa-chevron-up', !isCollapsed);
            icon.classList.toggle('fa-chevron-down', isCollapsed);
        }

        if (persist) {
            const collapsedSections = getCollapsedSidebarSections();
            collapsedSections[sectionKey] = isCollapsed;
            localStorage.setItem(sidebarSectionsCollapsedStorageKey, JSON.stringify(collapsedSections));
        }
    }

    function initSidebarSectionToggles() {
        const collapsedSections = getCollapsedSidebarSections();
        document.querySelectorAll('[data-nav-section-toggle]').forEach(toggle => {
            const sectionKey = toggle.dataset.navSectionToggle;
            setSidebarSectionCollapsed(toggle, collapsedSections[sectionKey] === true, {persist: false});
            toggle.addEventListener('click', function () {
                const section = this.closest('.nav-section');
                setSidebarSectionCollapsed(this, !section?.classList.contains('collapsed'));
            });
        });
    }

    // ============================
    // CONNECTION MANAGER
    // ============================
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }



    function getAllSidebarPages() {
        return Array.from(document.querySelectorAll('.nav-item[data-page]')).map(item => item.dataset.page);
    }

    function normalizeSidebarPages(pageIds) {
        const allPages = getAllSidebarPages();
        const visiblePages = Array.isArray(pageIds) ? pageIds.filter(page => allPages.includes(page)) : allPages;
        return visiblePages.length ? visiblePages : allPages;
    }

    function getVisibleSidebarPages() {
        return normalizeSidebarPages(currentDbUser?.sidebar_visible_tabs);
    }

    function getAllSidebarSections() {
        return Array.from(document.querySelectorAll('.sidebar-nav > [data-sidebar-section]')).map(section => section.dataset.sidebarSection);
    }

    function normalizeSidebarSections(sectionIds) {
        const allSections = getAllSidebarSections();
        const normalized = Array.isArray(sectionIds)
            ? Array.from(new Set(sectionIds.filter(sectionId => allSections.includes(sectionId))))
            : [];
        normalized.push(...allSections.filter(sectionId => !normalized.includes(sectionId)));
        return normalized;
    }

    function applySidebarSectionOrder(sectionIds) {
        const sidebarNav = document.querySelector('.sidebar-nav');
        if (!sidebarNav) return;
        const sections = new Map(Array.from(sidebarNav.querySelectorAll(':scope > [data-sidebar-section]')).map(section => [section.dataset.sidebarSection, section]));
        normalizeSidebarSections(sectionIds).forEach(sectionId => sidebarNav.appendChild(sections.get(sectionId)));
    }

    function applySidebarPageOrder(pageIds) {
        const order = new Map(normalizeSidebarPages(pageIds).map((pageId, index) => [pageId, index]));
        document.querySelectorAll('.sidebar-nav .nav-section').forEach(container => {
            const items = Array.from(container.querySelectorAll(':scope > .nav-item[data-page]'));
            items.sort((first, second) => {
                const firstOrder = order.has(first.dataset.page) ? order.get(first.dataset.page) : Number.MAX_SAFE_INTEGER;
                const secondOrder = order.has(second.dataset.page) ? order.get(second.dataset.page) : Number.MAX_SAFE_INTEGER;
                return firstOrder - secondOrder;
            });
            items.forEach(item => container.appendChild(item));
        });
    }

    function saveSidebarSettings(pageIds, sectionIds) {
        const visiblePages = normalizeSidebarPages(pageIds);
        if (!visiblePages.length) return Promise.reject(new Error('Выберите хотя бы одну вкладку для сайдбара'));

        return connectionRequest(sidebarSettingsApiUrl, {visible_tabs: visiblePages, section_order: normalizeSidebarSections(sectionIds)}).then(data => {
            currentDbUser.sidebar_visible_tabs = normalizeSidebarPages(data.visible_tabs);
            currentDbUser.sidebar_section_order = normalizeSidebarSections(data.section_order);
            return data;
        });
    }

    function renderSidebarSettingsList() {
        const list = document.getElementById('sidebarSettingsList');
        if (!list) return;

        const visiblePages = new Set(getVisibleSidebarPages());
        list.innerHTML = '';
        const appendSettingsItem = (item, groupItems) => {
            const pageId = item.dataset.page;
            const label = item.getAttribute('title') || item.textContent.trim() || pageId;
            const icon = item.querySelector('.nav-icon')?.cloneNode(true);
            const inputId = `sidebar-setting-${pageId}`;
            const isFixed = item.hasAttribute('data-fixed-page');
            const row = document.createElement('div');
            row.className = 'sidebar-settings-item';
            row.dataset.sidebarPage = pageId;
            row.dataset.fixedPage = String(isFixed);
            const dragTabLabel = translateInterfaceText('Перетащить вкладку');
            row.innerHTML = `
                ${isFixed ? '<span class="sidebar-settings-item__fixed-space" aria-hidden="true"></span>' : `<input class="form-check-input" id="${escapeHtml(inputId)}" type="checkbox" value="${escapeHtml(pageId)}" ${visiblePages.has(pageId) ? 'checked' : ''}>`}
                <span class="sidebar-settings-item__icon"></span>
                ${isFixed ? `<span>${escapeHtml(label)}</span>` : `<label for="${escapeHtml(inputId)}">${escapeHtml(label)}</label>`}
                <span class="sidebar-settings-item__drag-handle" draggable="true" data-sidebar-drag-handle title="${dragTabLabel}" aria-label="${dragTabLabel}" role="button" tabindex="0"><i class="fas fa-grip-vertical" aria-hidden="true"></i></span>
            `;
            if (icon) row.querySelector('.sidebar-settings-item__icon').appendChild(icon);
            groupItems.appendChild(row);
        };
        const appendSettingsGroup = (label, items) => {
            if (!items.length) return;
            const group = document.createElement('section');
            const sectionId = items[0].closest('[data-sidebar-section]')?.dataset.sidebarSection;
            group.className = 'sidebar-settings-group';
            group.dataset.sidebarSection = sectionId;
            const dragSectionTitle = translateInterfaceText('Перетащить блок');
            const dragSectionAriaLabel = translateInterfaceText(`Перетащить блок ${escapeHtml(translateInterfaceText(label))}`);
            group.innerHTML = `<h6 class="sidebar-settings-group__title" draggable="true" data-sidebar-group-drag-handle tabindex="0" role="button" title="${dragSectionTitle}" aria-label="${dragSectionAriaLabel}"><span>${escapeHtml(label)}</span><i class="fas fa-grip-vertical" aria-hidden="true"></i></h6><div class="sidebar-settings-group__items"></div>`;
            const groupItems = group.querySelector('.sidebar-settings-group__items');
            items.forEach(item => appendSettingsItem(item, groupItems));
            list.appendChild(group);
        };

        normalizeSidebarSections(currentDbUser?.sidebar_section_order).forEach(sectionId => {
            const section = document.querySelector(`.sidebar-nav > [data-sidebar-section="${sectionId}"]`);
            if (!section) return;
            const label = section.querySelector('.nav-section-title span')?.textContent.trim() || '';
            const items = Array.from(section.querySelectorAll('.nav-item[data-page]'));
            appendSettingsGroup(label, items);
        });
    }

    function initSettingsTabs() {
        const tabs = Array.from(document.querySelectorAll('[data-settings-tab]'));
        const panels = Array.from(document.querySelectorAll('[data-settings-panel]'));
        if (!tabs.length || !panels.length) return;

        const activateTab = tabName => {
            if (!tabs.some(tab => tab.dataset.settingsTab === tabName)) return;

            tabs.forEach(tab => {
                const active = tab.dataset.settingsTab === tabName;
                tab.classList.toggle('active', active);
                tab.setAttribute('aria-selected', String(active));
                tab.tabIndex = active ? 0 : -1;
            });
            panels.forEach(panel => {
                const active = panel.dataset.settingsPanel === tabName;
                panel.classList.toggle('active', active);
                panel.hidden = !active;
            });
            sessionStorage.setItem(activeSettingsTabStorageKey, tabName);
        };

        tabs.forEach((tab, index) => {
            tab.addEventListener('click', () => activateTab(tab.dataset.settingsTab));
            tab.addEventListener('keydown', event => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                let nextIndex = index;
                if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
                if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
                if (event.key === 'Home') nextIndex = 0;
                if (event.key === 'End') nextIndex = tabs.length - 1;
                activateTab(tabs[nextIndex].dataset.settingsTab);
                tabs[nextIndex].focus();
            });
        });
        const requestedTab = sessionStorage.getItem(activeSettingsTabStorageKey);
        const initialTab = tabs.some(tab => tab.dataset.settingsTab === requestedTab)
            ? requestedTab
            : tabs.find(tab => tab.classList.contains('active'))?.dataset.settingsTab || tabs[0].dataset.settingsTab;
        activateTab(initialTab);
    }

    function initPaginationSettingsEditor() {
        const form = document.getElementById('paginationSettingsForm');
        const list = document.getElementById('paginationSettingsList');
        if (!form || !list) return;
        const idInput = document.getElementById('paginationSettingId');
        const sizeInput = document.getElementById('paginationSettingSize');
        const cancelButton = document.getElementById('paginationSettingCancelBtn');
        const showValidationError = message => {
            document.getElementById('paginationValidationModalMessage').textContent = translateInterfaceText(message);
            bootstrap.Modal.getOrCreateInstance(document.getElementById('paginationValidationModal')).show();
        };
        const reloadPaginationSettings = () => {
            window.location.reload();
        };
        const resetForm = () => {
            form.reset();
            idInput.value = '';
            cancelButton.hidden = true;
        };
        const request = (method, payload) => fetch(paginationSettingsApiUrl, {
            method,
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
            body: payload ? JSON.stringify(payload) : undefined
        }).then(async response => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.ok === false) throw new Error(data.message || 'Ошибка запроса');
            return data;
        });
        const loadSettings = () => request('GET').then(data => {
            list.innerHTML = (data.settings || []).map(item => `
                <div class="pagination-settings-item">
                    <strong>${escapeHtml(item.size)}</strong>
                    <div>
                        <button class="btn btn-sm btn-outline-primary" type="button" data-pagination-edit="${escapeHtml(item.id)}" data-pagination-size="${escapeHtml(item.size)}"><i class="fas fa-edit"></i> Редактировать</button>
                        <button class="btn btn-sm btn-outline-danger" type="button" data-pagination-delete="${escapeHtml(item.id)}"><i class="fas fa-trash"></i> Удалить</button>
                    </div>
                </div>`).join('');
            if ((data.settings || []).length >= data.max_records) sizeInput.disabled = !idInput.value;
        }).catch(error => { list.innerHTML = `<div class="text-danger">${escapeHtml(error.message)}</div>`; });
        form.addEventListener('submit', event => {
            event.preventDefault();
            request('POST', {id: idInput.value || null, size: sizeInput.value})
                .then(reloadPaginationSettings)
                .catch(error => showValidationError(error.message));
        });
        cancelButton.addEventListener('click', () => { resetForm(); loadSettings(); });
        list.addEventListener('click', event => {
            const editButton = event.target.closest('[data-pagination-edit]');
            const deleteButton = event.target.closest('[data-pagination-delete]');
            if (editButton) {
                idInput.value = editButton.dataset.paginationEdit;
                sizeInput.value = editButton.dataset.paginationSize;
                sizeInput.disabled = false;
                cancelButton.hidden = false;
                sizeInput.focus();
            } else if (deleteButton && window.confirm(translateInterfaceText('Удалить настройку пагинации?'))) {
                request('DELETE', {id: deleteButton.dataset.paginationDelete})
                    .then(reloadPaginationSettings)
                    .catch(error => showValidationError(error.message));
            }
        });
        loadSettings();
    }

    function initReportsSettings() {
        const body = document.getElementById('reportsSettingsBody');
        const sortButton = document.getElementById('reportsDateSortBtn');
        const pageSizeSelect = document.getElementById('reportsPageSizeSelect');
        const previousButton = document.getElementById('reportsPrevPageBtn');
        const nextButton = document.getElementById('reportsNextPageBtn');
        const paginationInfo = document.getElementById('reportsPaginationInfo');
        const filters = {
            date: document.getElementById('reportsDateFilter'),
            connection: document.getElementById('reportsConnectionFilter'),
            database: document.getElementById('reportsDatabaseFilter'),
            user: document.getElementById('reportsUserFilter'),
            language: document.getElementById('reportsLanguageFilter'),
            status: document.getElementById('reportsStatusFilter')
        };
        if (!body || !sortButton || !pageSizeSelect || !previousButton || !nextButton || !paginationInfo || Object.values(filters).some(filter => !filter)) return;

        let reports = [];
        const storedPageSize = Number(localStorage.getItem('db_stat_page_size_reports'));
        const pagination = {page: 1, pageSize: paginationPageSizeOptions.includes(storedPageSize) ? storedPageSize : defaultPaginationPageSize};
        pageSizeSelect.innerHTML = paginationPageSizeOptions.map(size => `<option value="${size}">${size}</option>`).join('');
        pageSizeSelect.value = String(pagination.pageSize);
        const statusLabels = {queued: 'В очереди', running: 'Формируется', completed: 'Готов', failed: 'Ошибка'};
        const formatDateTime = value => {
            const date = value ? new Date(value) : null;
            return date && !Number.isNaN(date.getTime()) ? date.toLocaleString() : '—';
        };
        const formatLocalDate = value => {
            const date = value ? new Date(value) : null;
            if (!date || Number.isNaN(date.getTime())) return '';
            const pad = number => String(number).padStart(2, '0');
            return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
        };
        const setFilterOptions = (select, values, labelFor = value => value) => {
            const selected = select.value;
            select.replaceChildren(new Option(translateInterfaceText('Все'), ''));
            values.forEach(value => select.add(new Option(translateInterfaceText(labelFor(value)), value)));
            if (values.includes(selected)) select.value = selected;
        };
        const updateFilterOptions = () => {
            const unique = key => [...new Set(reports.map(report => String(report[key] || '')).filter(Boolean))].sort((a, b) => a.localeCompare(b));
            setFilterOptions(filters.connection, unique('connection_name'));
            setFilterOptions(filters.database, unique('database'));
            setFilterOptions(filters.user, unique('username'));
            setFilterOptions(filters.language, unique('language'), value => value.toUpperCase());
            setFilterOptions(filters.status, unique('status'), value => statusLabels[value] || value);
        };
        const render = () => {
            const multiplier = sortButton.dataset.direction === 'asc' ? 1 : -1;
            const filtered = reports.filter(report =>
                (!filters.date.value || formatLocalDate(report.created) === filters.date.value)
                && (!filters.connection.value || report.connection_name === filters.connection.value)
                && (!filters.database.value || report.database === filters.database.value)
                && (!filters.user.value || report.username === filters.user.value)
                && (!filters.language.value || report.language === filters.language.value)
                && (!filters.status.value || report.status === filters.status.value)
            );
            const sorted = [...filtered].sort((first, second) => multiplier * (new Date(first.created).getTime() - new Date(second.created).getTime()));
            const totalPages = Math.max(Math.ceil(sorted.length / pagination.pageSize), 1);
            pagination.page = Math.min(pagination.page, totalPages);
            const pageReports = sorted.slice((pagination.page - 1) * pagination.pageSize, pagination.page * pagination.pageSize);
            paginationInfo.textContent = `Страница ${pagination.page} из ${totalPages}`;
            previousButton.disabled = pagination.page <= 1;
            nextButton.disabled = pagination.page >= totalPages;
            sortButton.querySelector('i').className = `fas fa-sort-${sortButton.dataset.direction === 'asc' ? 'up' : 'down'}`;
            sortButton.setAttribute('aria-label', sortButton.dataset.direction === 'asc' ? 'Дата: сначала старые' : 'Дата: сначала новые');
            if (!sorted.length) {
                const emptyMessage = reports.length ? 'Отчёты по фильтрам не найдены' : 'PDF-отчёты пока не создавались';
                body.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">${escapeHtml(translateInterfaceText(emptyMessage))}</td></tr>`;
                return;
            }
            body.innerHTML = pageReports.map(report => {
                const download = report.download_url
                    ? `<a class="btn btn-sm btn-outline-primary" href="${escapeHtml(report.download_url)}"><i class="fas fa-download" aria-hidden="true"></i> Скачать</a>`
                    : '<span class="text-muted">—</span>';
                const duration = report.duration_seconds == null ? '—' : `${Number(report.duration_seconds).toLocaleString()} с`;
                return `<tr>
                    <td data-label="Дата">${escapeHtml(formatDateTime(report.created))}</td>
                    <td data-label="Подключение">${escapeHtml(report.connection_name || '—')}</td>
                    <td data-label="База данных">${escapeHtml(report.database || '—')}</td>
                    <td data-label="Пользователь">${escapeHtml(report.username || '—')}</td>
                    <td data-label="Язык">${escapeHtml(String(report.language || '—').toUpperCase())}</td>
                    <td data-label="Статус"><span class="report-status report-status--${escapeHtml(report.status)}">${escapeHtml(statusLabels[report.status] || report.status)}</span></td>
                    <td data-label="Длительность">${escapeHtml(duration)}</td>
                    <td data-label="Файл">${download}</td>
                </tr>`;
            }).join('');
        };
        const load = async () => {
            try {
                const response = await fetch(databasePdfReportApiUrl);
                const data = await response.json().catch(() => ({}));
                if (!response.ok || data.ok === false) throw new Error(data.message || 'Не удалось загрузить PDF-отчёты');
                reports = data.reports || [];
                updateFilterOptions();
                render();
            } catch (error) {
                body.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">${escapeHtml(error.message)}</td></tr>`;
            }
        };
        sortButton.addEventListener('click', () => {
            sortButton.dataset.direction = sortButton.dataset.direction === 'desc' ? 'asc' : 'desc';
            pagination.page = 1;
            render();
        });
        Object.values(filters).forEach(filter => filter.addEventListener('change', () => {
            pagination.page = 1;
            render();
        }));
        pageSizeSelect.addEventListener('change', () => {
            pagination.pageSize = Number(pageSizeSelect.value) || defaultPaginationPageSize;
            pagination.page = 1;
            localStorage.setItem('db_stat_page_size_reports', String(pagination.pageSize));
            render();
        });
        previousButton.addEventListener('click', () => {
            if (pagination.page > 1) {
                pagination.page -= 1;
                render();
            }
        });
        nextButton.addEventListener('click', () => {
            pagination.page += 1;
            render();
        });
        document.getElementById('settingsReportsTab')?.addEventListener('click', load);
        document.addEventListener('dbstat:reports-changed', load);
        window.setInterval(() => {
            if (!document.hidden && !document.getElementById('settingsReportsPanel').hidden) load();
        }, 5000);
        load();
    }

    function initSidebarSettings() {
        const settingsList = document.getElementById('sidebarSettingsList');
        if (!settingsList) return;

        renderSidebarSettingsList();

        let draggedItem = null;
        let draggedGroup = null;
        settingsList.addEventListener('dragstart', function (event) {
            const groupHandle = event.target.closest('[data-sidebar-group-drag-handle]');
            if (groupHandle) {
                draggedGroup = groupHandle.closest('.sidebar-settings-group');
                draggedGroup.classList.add('dragging');
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('text/plain', draggedGroup.dataset.sidebarSection || '');
                return;
            }
            const handle = event.target.closest('[data-sidebar-drag-handle]');
            draggedItem = handle?.closest('.sidebar-settings-item') || null;
            if (!draggedItem) return;
            draggedItem.classList.add('dragging');
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', draggedItem.querySelector('input')?.value || '');
        });
        settingsList.addEventListener('dragover', function (event) {
            const targetGroup = event.target.closest('.sidebar-settings-group');
            if (draggedGroup && targetGroup && targetGroup !== draggedGroup) {
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                const targetBox = targetGroup.getBoundingClientRect();
                const insertAfter = event.clientX > targetBox.left + targetBox.width / 2 || event.clientY > targetBox.top + targetBox.height / 2;
                settingsList.insertBefore(draggedGroup, insertAfter ? targetGroup.nextElementSibling : targetGroup);
                return;
            }
            const targetItem = event.target.closest('.sidebar-settings-item');
            if (!draggedItem || !targetItem || targetItem === draggedItem || targetItem.parentElement !== draggedItem.parentElement) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            const targetBox = targetItem.getBoundingClientRect();
            const insertAfter = event.clientY > targetBox.top + targetBox.height / 2;
            targetItem.parentElement.insertBefore(draggedItem, insertAfter ? targetItem.nextElementSibling : targetItem);
        });
        settingsList.addEventListener('drop', function (event) {
            if (draggedItem || draggedGroup) event.preventDefault();
        });
        settingsList.addEventListener('dragend', function () {
            draggedItem?.classList.remove('dragging');
            draggedGroup?.classList.remove('dragging');
            draggedItem = null;
            draggedGroup = null;
        });
        settingsList.addEventListener('keydown', function (event) {
            const groupHandle = event.target.closest('[data-sidebar-group-drag-handle]');
            if (groupHandle && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
                const group = groupHandle.closest('.sidebar-settings-group');
                const moveBack = ['ArrowLeft', 'ArrowUp'].includes(event.key);
                const sibling = moveBack ? group.previousElementSibling : group.nextElementSibling;
                if (!sibling) return;
                event.preventDefault();
                settingsList.insertBefore(group, moveBack ? sibling : sibling.nextElementSibling);
                groupHandle.focus();
                return;
            }
            const handle = event.target.closest('[data-sidebar-drag-handle]');
            if (!handle || !['ArrowUp', 'ArrowDown'].includes(event.key)) return;
            const item = handle.closest('.sidebar-settings-item');
            const sibling = event.key === 'ArrowUp' ? item.previousElementSibling : item.nextElementSibling;
            if (!sibling) return;
            event.preventDefault();
            if (event.key === 'ArrowUp') {
                item.parentElement.insertBefore(item, sibling);
            } else {
                item.parentElement.insertBefore(sibling, item);
            }
            handle.focus();
        });

        document.getElementById('sidebarSettingsSelectAllBtn')?.addEventListener('click', function () {
            document.querySelectorAll('#sidebarSettingsList input[type="checkbox"]').forEach(input => {
                input.checked = true;
            });
        });

        document.getElementById('sidebarSettingsSaveBtn')?.addEventListener('click', function () {
            const selectedPages = Array.from(document.querySelectorAll('#sidebarSettingsList .sidebar-settings-item'))
                .filter(item => item.dataset.fixedPage === 'true' || item.querySelector('input[type="checkbox"]:checked'))
                .map(item => item.dataset.sidebarPage);
            const sectionOrder = Array.from(document.querySelectorAll('#sidebarSettingsList .sidebar-settings-group'))
                .map(group => group.dataset.sidebarSection);
            if (!selectedPages.some(pageId => pageId !== 'settings')) {
                showToast('⚠️ Выберите хотя бы одну вкладку для сайдбара');
                return;
            }

            saveSidebarSettings(selectedPages, sectionOrder)
                .then(() => {
                    applySidebarPageOrder(currentDbUser.sidebar_visible_tabs);
                    applySidebarSectionOrder(currentDbUser.sidebar_section_order);
                    updateSidebarForConnection();
                    if (!isKnownPage(getCurrentActivePageId())) {
                        activatePage(getDefaultPageForConnection());
                    }
                    renderSidebarSettingsList();
                    showToast('✅ Настройки сайдбара сохранены');
                })
                .catch(error => showToast(`❌ ${error.message || 'Не удалось сохранить настройки сайдбара'}`));
        });
    }

    function initLanguageSettings() {
        const languageSelect = document.getElementById('interfaceLanguage');
        const saveButton = document.getElementById('interfaceLanguageSaveBtn');
        if (!languageSelect || !saveButton) return;

        languageSelect.value = window.DBStatI18n?.language || 'ru';
        saveButton.addEventListener('click', function () {
            const selectedLanguage = languageSelect.value || 'ru';
            if (selectedLanguage === (window.DBStatI18n?.language || 'ru')) {
                showToast('✅ Язык интерфейса сохранён');
                return;
            }
            connectionRequest(languageSettingsApiUrl, {language: selectedLanguage})
                .then(() => window.location.reload())
                .catch(error => showToast(`❌ ${error.message || 'Не удалось сохранить язык интерфейса'}`));
        });
    }

    function initThemeSettings() {
        const inputs = Array.from(document.querySelectorAll('input[name="interfaceTheme"]'));
        if (!inputs.length || !window.DBStatTheme) return;

        const syncSelection = theme => {
            inputs.forEach(input => {
                const selected = input.value === theme;
                input.checked = selected;
                input.closest('.theme-option')?.classList.toggle('selected', selected);
            });
        };

        syncSelection(window.DBStatTheme.get());
        inputs.forEach(input => input.addEventListener('change', function () {
            if (!this.checked) return;
            const theme = window.DBStatTheme.apply(this.value);
            syncSelection(theme);
            showToast('✅ Тема оформления сохранена');
        }));
        document.addEventListener('dbstat:themechange', event => syncSelection(event.detail.theme));
    }

    function initLogoutForm() {
        const logoutForm = document.getElementById('logoutForm');
        if (!logoutForm) return;

        logoutForm.addEventListener('submit', function () {
            const csrfToken = getCookie('csrftoken');
            const csrfInput = logoutForm.querySelector('input[name="csrfmiddlewaretoken"]');
            if (csrfToken && csrfInput) {
                csrfInput.value = csrfToken;
            }
        });
    }

    function initSessionCountdown() {
        const countdown = document.getElementById('sessionCountdown');
        const value = document.getElementById('sessionCountdownValue');
        const expiresAt = Number(countdown?.dataset.expiresAt || 0);
        if (!countdown || !value || !expiresAt) return;

        let logoutStarted = false;
        const finishSession = () => {
            if (logoutStarted) return;
            logoutStarted = true;
            window.clearInterval(timerId);
            countdown.classList.add('expired');
            const logoutForm = document.getElementById('logoutForm');
            if (logoutForm) {
                logoutForm.requestSubmit();
                return;
            }
            window.location.replace('/login/');
        };
        const updateCountdown = () => {
            const remainingSeconds = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
            const hours = Math.floor(remainingSeconds / 3600);
            const minutes = Math.floor((remainingSeconds % 3600) / 60);
            const seconds = remainingSeconds % 60;
            value.textContent = [hours, minutes, seconds].map(part => String(part).padStart(2, '0')).join(':');
            if (remainingSeconds === 0) {
                finishSession();
            }
        };
        const timerId = window.setInterval(updateCountdown, 1000);
        updateCountdown();
    }

    function getConnectionFormData() {
        return {
            id: document.getElementById('connId').value,
            name: document.getElementById('connName').value.trim(),
            host: document.getElementById('connHost').value.trim(),
            port: parseInt(document.getElementById('connPort').value),
            database: document.getElementById('connDatabase').value.trim(),
            user: document.getElementById('connUser').value.trim(),
            password: document.getElementById('connPassword').value,
            db_type: document.getElementById('connDbType').value
        };
    }

    function updateConnectionDbTypeIcon() {
        const select = document.getElementById('connDbType');
        const icon = document.getElementById('connDbTypeIcon');
        const label = document.getElementById('connDbTypeLabel');
        const selectedOption = select?.selectedOptions?.[0];
        if (!select || !icon || !label || !selectedOption) return;

        const dbType = selectedOption.value;
        const iconSrc = selectedOption.dataset.icon;

        if (iconSrc) icon.src = iconSrc;
        icon.alt = '';
        label.textContent = dbType;

        document.querySelectorAll('.db-type-select__option').forEach(option => {
            const isSelected = option.dataset.value === dbType;
            option.classList.toggle('is-selected', isSelected);
            option.setAttribute('aria-selected', String(isSelected));
        });
    }

    function setConnectionDbType(value) {
        const select = document.getElementById('connDbType');
        if (!select) return;

        select.value = value || 'PostgreSQL';
        if (!select.value) {
            select.value = 'PostgreSQL';
        }
        updateConnectionDbTypeIcon();
    }

    function initConnectionDbTypeSelect() {
        const wrapper = document.querySelector('.db-type-select');
        const toggle = document.getElementById('connDbTypeToggle');
        const select = document.getElementById('connDbType');
        if (!wrapper || !toggle || !select) return;

        const closeMenu = () => {
            wrapper.classList.remove('open');
            toggle.setAttribute('aria-expanded', 'false');
        };

        const openMenu = () => {
            wrapper.classList.add('open');
            toggle.setAttribute('aria-expanded', 'true');
        };

        toggle.addEventListener('click', function () {
            if (wrapper.classList.contains('open')) {
                closeMenu();
            } else {
                openMenu();
            }
        });

        document.querySelectorAll('.db-type-select__option').forEach(option => {
            option.addEventListener('click', function () {
                setConnectionDbType(this.dataset.value);
                closeMenu();
                toggle.focus();
            });
        });

        document.addEventListener('click', function (event) {
            if (!wrapper.contains(event.target)) {
                closeMenu();
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeMenu();
            }
        });
    }

    function validateConnectionPayload(payload) {
        return payload.name && payload.host && payload.port && payload.database && payload.user;
    }

    function formatDatabaseSize(sizeBytes) {
        const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        let value = Number(sizeBytes) || 0;
        let unitIndex = 0;
        while (value >= 1024 && unitIndex < units.length - 1) {
            value /= 1024;
            unitIndex += 1;
        }
        const precision = value >= 100 || unitIndex === 0 ? 0 : value >= 10 ? 1 : 2;
        return {value: value.toFixed(precision), unit: units[unitIndex]};
    }

    function translateInterfaceText(value) {
        return window.DBStatI18n?.translate(String(value ?? '')) ?? String(value ?? '');
    }

    function getConnectionSlotValue(connectionSlots, key) {
        const item = connectionSlots.find(slot => slot.key === key);
        return item ? item.value : null;
    }

    function updateConnectionSlotsChart(connectionSlots) {
        const donut = document.getElementById('databaseOverviewConnectionSlotsDonut');
        const summary = document.getElementById('databaseOverviewConnectionSlotsSummary');
        if (!donut || !summary) return;

        const current = Number(getConnectionSlotValue(connectionSlots, 'current_connections')) || 0;
        const maximum = Number(getConnectionSlotValue(connectionSlots, 'max_connections')) || 0;
        const rawUsage = Number(getConnectionSlotValue(connectionSlots, 'usage_percent')) || 0;
        const usage = Math.max(0, Math.min(rawUsage, 100));
        const usageText = rawUsage.toFixed(2);

        donut.style.setProperty('--connection-slots-usage', `${usage}%`);
        donut.setAttribute('aria-label', translateInterfaceText(`Использование слотов подключений: ${current} из ${maximum}, ${usageText}%`));
        summary.textContent = maximum > 0 ? translateInterfaceText(`${current} из ${maximum}`) : '—';
    }


    function getActivityStatValue(activityStats, key) {
        const item = activityStats.find(stat => stat.key === key);
        return item ? item.value : null;
    }

    function updateDatabaseActivityChart(activityStats) {
        const donut = document.getElementById('databaseOverviewActivityDonut');
        const summary = document.getElementById('databaseOverviewActivitySummary');
        if (!donut || !summary) return;

        const commits = Number(getActivityStatValue(activityStats, 'xact_commit')) || 0;
        const rollbacks = Number(getActivityStatValue(activityStats, 'xact_rollback')) || 0;
        const total = commits + rollbacks;
        const commitPercent = total > 0 ? Math.max(0, Math.min((commits / total) * 100, 100)) : 0;
        const rollbackPercent = total > 0 ? Math.max(0, Math.min((rollbacks / total) * 100, 100)) : 0;
        const commitText = commitPercent.toFixed(2);
        const rollbackText = rollbackPercent.toFixed(2);

        donut.style.setProperty('--db-activity-commit', `${commitPercent}%`);
        donut.style.setProperty('--db-activity-rollback', `${commitPercent + rollbackPercent}%`);
        donut.setAttribute('aria-label', translateInterfaceText(`Активность БД: коммиты ${commitText}%, роллбеки ${rollbackText}%`));
        summary.textContent = total > 0
            ? `${commits} / ${rollbacks}` : '—';
    }

    function renderDatabaseOverviewWarning(message) {
        message = translateInterfaceText(message);
        const tbody = document.getElementById('databaseOverviewTableBody');
        const memoryTbody = document.getElementById('databaseOverviewMemoryTableBody');
        const connectionTbody = document.getElementById('databaseOverviewConnectionTableBody');
        const rolesTbody = document.getElementById('databaseOverviewRolesTableBody');
        const connectionSlotsTbody = document.getElementById('databaseOverviewConnectionSlotsTableBody');
        const basicSettingsTbody = document.getElementById('databaseOverviewBasicSettingsTableBody');
        const activityStatsTbody = document.getElementById('databaseOverviewActivityTableBody');
        const extensionsTbody = document.getElementById('databaseOverviewExtensionsTableBody');
        const count = document.getElementById('databaseOverviewCount');
        const memoryCount = document.getElementById('databaseOverviewMemoryCount');
        const connectionCount = document.getElementById('databaseOverviewConnectionCount');
        const rolesCount = document.getElementById('databaseOverviewRolesCount');
        const connectionSlotsCount = document.getElementById('databaseOverviewConnectionSlotsCount');
        const basicSettingsCount = document.getElementById('databaseOverviewBasicSettingsCount');
        const activityStatsCount = document.getElementById('databaseOverviewActivityCount');
        const extensionsCount = document.getElementById('databaseOverviewExtensionsCount');
        const version = document.getElementById('databaseOverviewVersion');
        const noData = translateInterfaceText('Нет данных');
        if (count) count.textContent = noData;
        if (memoryCount) memoryCount.textContent = noData;
        if (connectionCount) connectionCount.textContent = noData;
        if (rolesCount) rolesCount.textContent = noData;
        if (connectionSlotsCount) connectionSlotsCount.textContent = noData;
        if (basicSettingsCount) basicSettingsCount.textContent = noData;
        if (activityStatsCount) activityStatsCount.textContent = noData;
        if (extensionsCount) extensionsCount.textContent = noData;
        updateConnectionSlotsChart([]);
        updateDatabaseActivityChart([]);
        if (version) version.textContent = message;
        if (tbody) tbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (memoryTbody) memoryTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (connectionTbody) connectionTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (rolesTbody) rolesTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (connectionSlotsTbody) connectionSlotsTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (basicSettingsTbody) basicSettingsTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (activityStatsTbody) activityStatsTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (extensionsTbody) extensionsTbody.innerHTML = `<tr><td colspan="4" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderDatabaseOverview(data) {
        const tbody = document.getElementById('databaseOverviewTableBody');
        const memoryTbody = document.getElementById('databaseOverviewMemoryTableBody');
        const connectionTbody = document.getElementById('databaseOverviewConnectionTableBody');
        const rolesTbody = document.getElementById('databaseOverviewRolesTableBody');
        const connectionSlotsTbody = document.getElementById('databaseOverviewConnectionSlotsTableBody');
        const basicSettingsTbody = document.getElementById('databaseOverviewBasicSettingsTableBody');
        const activityStatsTbody = document.getElementById('databaseOverviewActivityTableBody');
        const extensionsTbody = document.getElementById('databaseOverviewExtensionsTableBody');
        const count = document.getElementById('databaseOverviewCount');
        const memoryCount = document.getElementById('databaseOverviewMemoryCount');
        const connectionCount = document.getElementById('databaseOverviewConnectionCount');
        const rolesCount = document.getElementById('databaseOverviewRolesCount');
        const connectionSlotsCount = document.getElementById('databaseOverviewConnectionSlotsCount');
        const basicSettingsCount = document.getElementById('databaseOverviewBasicSettingsCount');
        const activityStatsCount = document.getElementById('databaseOverviewActivityCount');
        const extensionsCount = document.getElementById('databaseOverviewExtensionsCount');
        const version = document.getElementById('databaseOverviewVersion');
        const metrics = data.metrics || [];
        const memorySettings = data.memory_settings || [];
        const connectionInfo = data.connection_info || [];
        const roleCounts = data.role_counts || [];
        const connectionSlots = data.connection_slots || [];
        const basicSettings = data.basic_settings || [];
        const activityStats = data.activity_stats || [];
        const installedExtensions = data.installed_extensions || [];
        if (count) count.textContent = translateInterfaceText(`${metrics.length} метрик`);
        if (memoryCount) memoryCount.textContent = translateInterfaceText(`${memorySettings.length} параметра`);
        if (connectionCount) connectionCount.textContent = translateInterfaceText(`${connectionInfo.length} параметров`);
        if (rolesCount) rolesCount.textContent = translateInterfaceText(`${roleCounts.length} показателя`);
        if (connectionSlotsCount) connectionSlotsCount.textContent = translateInterfaceText(`${connectionSlots.length} показателя`);
        if (basicSettingsCount) basicSettingsCount.textContent = translateInterfaceText(`${basicSettings.length} параметров`);
        if (activityStatsCount) activityStatsCount.textContent = translateInterfaceText(`${activityStats.length} показателей`);
        if (extensionsCount) extensionsCount.textContent = translateInterfaceText(`${installedExtensions.length} расширений`);
        if (version) version.textContent = data.database_version || '—';
        if (basicSettingsTbody) {
            if (!basicSettings.length) {
                basicSettingsTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных об основных данных БД</td></tr>';
            } else {
                basicSettingsTbody.innerHTML = basicSettings.map(item => `
                    <tr>
                        <td>${escapeHtml(translateInterfaceText(item.label))}</td>
                        <td><strong>${escapeHtml(item.value ?? '—')}</strong></td>
                    </tr>
                `).join('');
            }
        }

        updateDatabaseActivityChart(activityStats);
        if (activityStatsTbody) {
            if (!activityStats.length) {
                activityStatsTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных об активности БД</td></tr>';
            } else {
                activityStatsTbody.innerHTML = activityStats.map(item => `
                    <tr>
                        <td>${escapeHtml(translateInterfaceText(item.label))}</td>
                        <td><strong>${escapeHtml(item.value ?? '—')}</strong></td>
                    </tr>
                `).join('');
            }
        }
        if (connectionTbody) {
            if (!connectionInfo.length) {
                connectionTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных о подключении</td></tr>';
            } else {
                connectionTbody.innerHTML = connectionInfo.map(item => `
                    <tr>
                        <td>${escapeHtml(translateInterfaceText(item.label))}</td>
                        <td><strong>${escapeHtml(item.value ?? '—')}</strong></td>
                    </tr>
                `).join('');
            }
        }
        if (tbody) {
            if (!metrics.length) {
                tbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных о размерах БД</td></tr>';
            } else {
                tbody.innerHTML = metrics.map(item => {
                    const formatted = formatDatabaseSize(item.size_bytes);
                    return `
                        <tr>
                            <td>${escapeHtml(translateInterfaceText(item.label))}</td>
                            <td><strong>${formatted.value} ${formatted.unit}</strong></td>
                        </tr>
                    `;
                }).join('');
            }
        }
        if (memoryTbody) {
            if (!memorySettings.length) {
                memoryTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных о параметрах памяти</td></tr>';
            } else {
                memoryTbody.innerHTML = memorySettings.map(item => `
                    <tr>
                        <td>${escapeHtml(translateInterfaceText(item.label))}</td>
                        <td><strong>${escapeHtml(item.value)}</strong></td>
                    </tr>
                `).join('');
            }
        }
        if (rolesTbody) {
            if (!roleCounts.length) {
                rolesTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных о пользователях и группах</td></tr>';
            } else {
                rolesTbody.innerHTML = roleCounts.map(item => `
                    <tr>
                        <td>${escapeHtml(translateInterfaceText(item.label))}</td>
                        <td><strong>${escapeHtml(item.count ?? 0)}</strong></td>
                    </tr>
                `).join('');
            }
        }
        if (extensionsTbody) {
            if (!installedExtensions.length) {
                extensionsTbody.innerHTML = '<tr><td colspan="4" class="text-muted">Нет установленных расширений</td></tr>';
            } else {
                extensionsTbody.innerHTML = installedExtensions.map(item => `
                    <tr>
                        <td><strong>${escapeHtml(item.name ?? '—')}</strong></td>
                        <td>${escapeHtml(item.version ?? '—')}</td>
                        <td>${escapeHtml(item.schema ?? '—')}</td>
                        <td>${escapeHtml(item.description ?? '—')}</td>
                    </tr>
                `).join('');
            }
        }
        updateConnectionSlotsChart(connectionSlots);
        if (connectionSlotsTbody) {
            if (!connectionSlots.length) {
                connectionSlotsTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных о слотах подключений</td></tr>';
            } else {
                connectionSlotsTbody.innerHTML = connectionSlots.map(item => {
                    const value = item.key === 'usage_percent' && item.value !== null && item.value !== undefined
                        ? `${Number(item.value).toFixed(2)}%`
                        : (item.value ?? '—');
                    return `
                    <tr>
                        <td>${escapeHtml(translateInterfaceText(item.label))}</td>
                        <td><strong>${escapeHtml(value)}</strong></td>
                    </tr>
                `;
                }).join('');
            }
        }
    }

    function refreshDatabaseOverviewForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const requestId = ++databaseOverviewRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderDatabaseOverviewWarning('Выберите сохранённое подключение для загрузки размеров БД');
            return;
        }
        renderDatabaseOverviewWarning('Загрузка размеров БД...');
        connectionRequest(databaseOverviewApiUrl, {id: conn.id})
            .then(data => {
                if (requestId === databaseOverviewRequestId) renderDatabaseOverview(data);
            })
            .catch(error => {
                if (requestId === databaseOverviewRequestId) renderDatabaseOverviewWarning(error.message || 'Не удалось получить размеры БД');
            });
    }



    function syncActiveQueriesUserFilter() {
        const input = document.getElementById('activeQueriesUserFilter');
        activeQueriesState.username = input ? input.value.trim() : '';
    }

    function sortActiveQueries(queries) {
        const sort = activeQueriesState.sort;
        const direction = activeQueriesState.direction === 'asc' ? 1 : -1;
        return [...queries].sort((a, b) => {
            const aValue = sort === 'pid' || sort === 'duration_seconds'
                ? Number(a[sort]) || 0
                : String(a[sort] ?? '').toLowerCase();
            const bValue = sort === 'pid' || sort === 'duration_seconds'
                ? Number(b[sort]) || 0
                : String(b[sort] ?? '').toLowerCase();
            if (aValue < bValue) return -1 * direction;
            if (aValue > bValue) return 1 * direction;
            return 0;
        });
    }

    function updateActiveQueriesSortIndicators() {
        document.querySelectorAll('[data-active-query-sort]').forEach(button => {
            const isActive = button.dataset.activeQuerySort === activeQueriesState.sort;
            button.classList.toggle('active', isActive);
            updateSortHeaderState(button, isActive, activeQueriesState.direction);
        });
    }

    function scheduleActiveQueriesRefresh() {
        if (activeQueriesState.timer) {
            clearInterval(activeQueriesState.timer);
            activeQueriesState.timer = null;
        }
        if (!activeQueriesState.refreshInterval) return;
        activeQueriesState.timer = setInterval(() => {
            // Without this guard, a query slower than the poll interval means
            // the next tick fires another request on top of it instead of
            // waiting — piling up overlapping requests against the shared
            // connection pool (db/settings.py DB_CONNECTION_POOL_MAX_CONN)
            // instead of just running a bit behind schedule.
            if (!activeQueriesState.inFlight && !document.hidden && document.getElementById('page-queries')?.classList.contains('active')) {
                refreshActiveQueriesForConnection(undefined, {silent: true});
            }
        }, activeQueriesState.refreshInterval * 1000);
    }

    function initActiveQueriesControls() {
        document.getElementById('activeQueriesTableBody')?.addEventListener('click', event => {
            const button = event.target.closest('[data-active-query-pid]');
            if (button) terminateActiveQuery(button);
        });
        document.querySelectorAll('[data-active-query-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.activeQuerySort;
                if (activeQueriesState.sort === sort) {
                    activeQueriesState.direction = activeQueriesState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    activeQueriesState.sort = sort;
                    activeQueriesState.direction = ['pid', 'duration_seconds'].includes(sort) ? 'desc' : 'asc';
                }
                refreshActiveQueriesForConnection(undefined, {silent: true});
            });
        });
        document.getElementById('activeQueriesRefreshInterval')?.addEventListener('change', function () {
            activeQueriesState.refreshInterval = Number(this.value) || 0;
            scheduleActiveQueriesRefresh();
            refreshActiveQueriesForConnection(undefined, {silent: true});
        });
        let userFilterTimer;
        document.getElementById('activeQueriesUserFilter')?.addEventListener('input', function () {
            clearTimeout(userFilterTimer);
            userFilterTimer = setTimeout(() => {
                activeQueriesState.username = this.value.trim();
                refreshActiveQueriesForConnection(undefined, {silent: true});
            }, 350);
        });
        document.getElementById('activeQueriesRefreshBtn')?.addEventListener('click', function () {
            refreshActiveQueriesForConnection(undefined, {silent: false});
        });
        updateActiveQueriesSortIndicators();
    }

    function renderActiveQueriesWarning(message) {
        const tbody = document.getElementById('activeQueriesTableBody');
        const count = document.getElementById('activeQueriesCount');
        if (count) count.textContent = 'Нет данных';
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderActiveQueries(data) {
        const tbody = document.getElementById('activeQueriesTableBody');
        const count = document.getElementById('activeQueriesCount');
        const receivedQueries = data.queries || [];
        const connectionPrefix = `${activeConnectionId}:`;
        terminatedActiveQueryKeys.forEach(key => {
            if (!key.startsWith(connectionPrefix)) return;
            const pid = key.slice(connectionPrefix.length);
            if (!receivedQueries.some(query => String(query.pid) === pid)) terminatedActiveQueryKeys.delete(key);
        });
        const queries = sortActiveQueries(receivedQueries.filter(query => !terminatedActiveQueryKeys.has(backendTerminationKey(activeConnectionId, query.pid))));
        updateActiveQueriesSortIndicators();
        if (count) count.textContent = activeQueriesState.username
            ? `${queries.length} активных запросов для ${activeQueriesState.username}`
            : `${queries.length} активных запросов`;
        if (!tbody) return;
        if (!queries.length) {
            tbody.innerHTML = `<tr><td colspan="${canRunDestructiveActions() ? 7 : 6}" class="text-muted">Активные запросы не найдены</td></tr>`;
            return;
        }
        tbody.innerHTML = queries.map(query => `
            <tr>
                <td><strong>${escapeHtml(query.pid)}</strong></td>
                <td>${escapeHtml(query.username)}</td>
                <td>${escapeHtml(query.relation_name)}</td>
                <td><span class="status-badge up">${escapeHtml(query.state)}</span></td>
                <td>${escapeHtml(query.duration)}</td>
                <td style="max-width:360px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; color:var(--text-muted);" title="${escapeHtml(query.sql)}">${escapeHtml(query.sql)}</td>
                ${canRunDestructiveActions() ? `<td class="backend-terminate-actions"><button type="button" class="btn btn-sm btn-outline-danger active-query-terminate-btn" data-active-query-pid="${escapeHtml(query.pid)}" title="Завершить запрос PID ${escapeHtml(query.pid)}" aria-label="Завершить запрос PID ${escapeHtml(query.pid)}">Завершить</button></td>` : ''}
            </tr>
        `).join('');
    }

    // Одно окно подтверждения за раз: пока оно открыто, новые вызовы не открывают второе окно
    // и не добавляют второй обработчик на кнопку подтверждения.
    let backendConfirmationPending = false;

    function confirmBackendTermination(message) {
        const modalElement = document.getElementById('backendTerminationModal');
        const messageElement = document.getElementById('backendTerminationModalMessage');
        const confirmButton = document.getElementById('backendTerminationConfirmBtn');
        if (!modalElement || !messageElement || !confirmButton) return Promise.resolve(false);
        if (backendConfirmationPending) return Promise.resolve(false);
        backendConfirmationPending = true;

        messageElement.textContent = translateInterfaceText(message);
        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        return new Promise(resolve => {
            let resolved = false;
            const finish = result => {
                if (resolved) return;
                resolved = true;
                backendConfirmationPending = false;
                confirmButton.removeEventListener('click', confirm);
                modalElement.removeEventListener('hidden.bs.modal', cancel);
                resolve(result);
            };
            const confirm = () => {
                finish(true);
                modal.hide();
            };
            const cancel = () => finish(false);
            confirmButton.addEventListener('click', confirm);
            modalElement.addEventListener('hidden.bs.modal', cancel);
            modal.show();
        });
    }

    // Кнопка блокируется на время окна подтверждения: повторный клик по ней ничего не открывает
    // и не отправляет второй запрос на завершение того же процесса. Если действие отменено, кнопка снова доступна.
    function requestBackendTermination(button, message, action) {
        if (button.disabled) return;
        button.disabled = true;
        confirmBackendTermination(message).then(confirmed => {
            if (!confirmed) {
                button.disabled = false;
                return;
            }
            action();
        });
    }

    function terminateActiveQuery(button) {
        const pid = button.dataset.activeQueryPid;
        const conn = connections.find(item => String(item.id) === String(activeConnectionId));
        if (!conn || !/^\d+$/.test(String(conn.id)) || !/^\d+$/.test(String(pid))) return;
        requestBackendTermination(button, `Завершить активный запрос с PID ${pid}?`, () => {
            button.disabled = true;
            connectionRequest(terminateActiveQueryApiUrl, {id: conn.id, pid: Number(pid)})
                .then(data => {
                    terminatedActiveQueryKeys.add(backendTerminationKey(conn.id, pid));
                    button.closest('tr')?.remove();
                    showToast(`✅ ${data.message}`);
                    refreshActiveQueriesAfterTermination(conn);
                })
                .catch(error => {
                    button.disabled = false;
                    showToast(`❌ ${error.message || 'Не удалось завершить активный запрос'}`);
                });
        });
    }

    function refreshActiveQueriesAfterTermination(conn) {
        if (String(activeConnectionId) !== String(conn.id)) return;
        refreshActiveQueriesForConnection(conn, {silent: true});
        [500, 1500].forEach(delay => window.setTimeout(() => {
            if (String(activeConnectionId) === String(conn.id) && document.getElementById('page-queries')?.classList.contains('active')) {
                refreshActiveQueriesForConnection(conn, {silent: true});
            }
        }, delay));
    }

    function refreshActiveQueriesForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId)), options = {}) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderActiveQueriesWarning('Выберите сохранённое подключение для загрузки активных запросов');
            return;
        }
        syncActiveQueriesUserFilter();
        const requestId = ++activeQueriesRequestId;
        activeQueriesState.inFlight = true;
        if (!options.silent) renderActiveQueriesWarning('Загрузка активных запросов...');
        connectionRequest(activeQueriesApiUrl, {id: conn.id, username: activeQueriesState.username})
            .then(data => {
                if (requestId !== activeQueriesRequestId) return;
                renderActiveQueries(data);
            })
            .catch(error => {
                if (requestId !== activeQueriesRequestId) return;
                renderActiveQueriesWarning(error.message || 'Не удалось получить активные запросы');
            })
            .finally(() => { activeQueriesState.inFlight = false; });
    }



    function getActiveSessionStateLabel(state) {
        const stateLabels = {
            active: 'Активна',
            idle: 'Простаивает',
            'idle in transaction': 'Простой в транзакции',
            'idle in transaction (aborted)': 'Простой в отменённой транзакции',
            disabled: 'Отключена',
            fastpath: 'Fast path'
        };
        return stateLabels[String(state || '').toLowerCase()] || state || '—';
    }

    function sortActiveSessions(sessions) {
        const sort = activeSessionsState.sort;
        const direction = activeSessionsState.direction === 'asc' ? 1 : -1;
        const numericColumns = new Set(['pid', 'session_duration_seconds']);
        return [...sessions].sort((a, b) => {
            const aValue = numericColumns.has(sort)
                ? Number(a[sort]) || 0
                : String(a[sort] ?? '').toLowerCase();
            const bValue = numericColumns.has(sort)
                ? Number(b[sort]) || 0
                : String(b[sort] ?? '').toLowerCase();
            if (aValue < bValue) return -1 * direction;
            if (aValue > bValue) return 1 * direction;
            return 0;
        });
    }

    function updateActiveSessionsSortIndicators() {
        document.querySelectorAll('[data-active-session-sort]').forEach(button => {
            const isActive = button.dataset.activeSessionSort === activeSessionsState.sort;
            button.classList.toggle('active', isActive);
            updateSortHeaderState(button, isActive, activeSessionsState.direction);
        });
    }

    function syncActiveSessionsFilters() {
        const userInput = document.getElementById('activeSessionsUserFilter');
        const stateInput = document.getElementById('activeSessionsStateFilter');
        activeSessionsState.username = userInput ? userInput.value.trim() : '';
        activeSessionsState.state = stateInput ? stateInput.value.trim() : '';
    }

    function renderActiveSessionsWarning(message) {
        const tbody = document.getElementById('activeSessionsTableBody');
        const count = document.getElementById('activeSessionsCount');
        if (count) count.textContent = 'Нет данных';
        ['Total', 'Active', 'Idle', 'IdleXact', 'Users', 'Clients'].forEach(key => {
            const item = document.getElementById(`activeSessionsSummary${key}`);
            if (item) item.textContent = '—';
        });
        if (tbody) tbody.innerHTML = `<tr><td colspan="11" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderActiveSessions(data) {
        const tbody = document.getElementById('activeSessionsTableBody');
        const count = document.getElementById('activeSessionsCount');
        const receivedSessions = data.sessions || [];
        const connectionPrefix = `${activeConnectionId}:`;
        terminatedActiveSessionKeys.forEach(key => {
            if (!key.startsWith(connectionPrefix)) return;
            const pid = key.slice(connectionPrefix.length);
            if (!receivedSessions.some(session => String(session.pid) === pid)) terminatedActiveSessionKeys.delete(key);
        });
        const sessions = sortActiveSessions(receivedSessions.filter(session => !terminatedActiveSessionKeys.has(backendTerminationKey(activeConnectionId, session.pid))));
        const summary = data.summary || {};
        updateActiveSessionsSortIndicators();
        if (count) count.textContent = activeSessionsState.username
            ? `${sessions.length} сессий для ${activeSessionsState.username}`
            : `${sessions.length} сессий`;
        const values = {Total: summary.total, Active: summary.active, Idle: summary.idle, IdleXact: summary.idle_in_transaction, Users: summary.users, Clients: summary.clients};
        Object.entries(values).forEach(([key, value]) => {
            const item = document.getElementById(`activeSessionsSummary${key}`);
            if (item) item.textContent = value ?? 0;
        });
        if (!tbody) return;
        if (!sessions.length) {
            tbody.innerHTML = `<tr><td colspan="${canRunDestructiveActions() ? 11 : 10}" class="text-muted">Активные сессии и подключения не найдены</td></tr>`;
            return;
        }
        tbody.innerHTML = sessions.map(session => {
            const stateClass = session.state === 'active' ? 'up' : (session.state === 'idle in transaction' ? 'warning' : '');
            const clientAddr = session.client_addr ?? '—';
            const clientPort = session.client_port ?? '—';
            const client = `${clientAddr}${clientPort !== '—' ? ':' + clientPort : ''}`;
            return `
                <tr>
                    <td><strong>${escapeHtml(session.pid)}</strong></td>
                    <td>${escapeHtml(session.username)}</td>
                    <td>${escapeHtml(session.database)}</td>
                    <td>${escapeHtml(session.application_name)}</td>
                    <td>${escapeHtml(client)}</td>
                    <td><span class="status-badge ${stateClass}">${escapeHtml(getActiveSessionStateLabel(session.state))}</span></td>
                    <td>${escapeHtml(session.wait_event)}</td>
                    <td>${escapeHtml(session.backend_type)}</td>
                    <td>${escapeHtml(session.session_duration)}</td>
                    <td style="max-width:360px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; color:var(--text-muted);" title="${escapeHtml(session.sql)}">${escapeHtml(session.sql)}</td>
                    ${canRunDestructiveActions() ? `<td class="backend-terminate-actions"><button type="button" class="btn btn-sm btn-outline-danger active-session-terminate-btn" data-active-session-pid="${escapeHtml(session.pid)}" title="Завершить сессию PID ${escapeHtml(session.pid)}" aria-label="Завершить сессию PID ${escapeHtml(session.pid)}">Завершить</button></td>` : ''}
                </tr>
            `;
        }).join('');
    }

    function scheduleActiveSessionsRefresh() {
        if (activeSessionsState.timer) {
            clearInterval(activeSessionsState.timer);
            activeSessionsState.timer = null;
        }
        if (!activeSessionsState.refreshInterval) return;
        activeSessionsState.timer = setInterval(() => {
            if (!activeSessionsState.inFlight && !document.hidden && document.getElementById('page-sessions')?.classList.contains('active')) {
                refreshActiveSessionsForConnection(undefined, {silent: true});
            }
        }, activeSessionsState.refreshInterval * 1000);
    }

    function initActiveSessionsControls() {
        document.getElementById('activeSessionsTableBody')?.addEventListener('click', event => {
            const button = event.target.closest('[data-active-session-pid]');
            if (button) terminateActiveSession(button);
        });
        document.querySelectorAll('[data-active-session-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.activeSessionSort;
                if (activeSessionsState.sort === sort) {
                    activeSessionsState.direction = activeSessionsState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    activeSessionsState.sort = sort;
                    activeSessionsState.direction = ['pid', 'session_duration_seconds'].includes(sort) ? 'desc' : 'asc';
                }
                refreshActiveSessionsForConnection(undefined, {silent: true});
            });
        });
        updateActiveSessionsSortIndicators();
        document.getElementById('activeSessionsRefreshInterval')?.addEventListener('change', function () {
            activeSessionsState.refreshInterval = Number(this.value) || 0;
            scheduleActiveSessionsRefresh();
            refreshActiveSessionsForConnection(undefined, {silent: true});
        });
        document.getElementById('activeSessionsStateFilter')?.addEventListener('change', function () {
            activeSessionsState.state = this.value.trim();
            refreshActiveSessionsForConnection(undefined, {silent: true});
        });
        let userFilterTimer;
        document.getElementById('activeSessionsUserFilter')?.addEventListener('input', function () {
            clearTimeout(userFilterTimer);
            userFilterTimer = setTimeout(() => {
                activeSessionsState.username = this.value.trim();
                refreshActiveSessionsForConnection(undefined, {silent: true});
            }, 350);
        });
        document.getElementById('activeSessionsRefreshBtn')?.addEventListener('click', function () {
            refreshActiveSessionsForConnection(undefined, {silent: false});
        });
    }

    function terminateActiveSession(button) {
        const pid = button.dataset.activeSessionPid;
        const conn = connections.find(item => String(item.id) === String(activeConnectionId));
        if (!conn || !/^\d+$/.test(String(conn.id)) || !/^\d+$/.test(String(pid))) return;
        requestBackendTermination(button, `Завершить сессию пользователя с PID ${pid}?`, () => {
            button.disabled = true;
            connectionRequest(terminateActiveSessionApiUrl, {id: conn.id, pid: Number(pid)})
                .then(data => {
                    terminatedActiveSessionKeys.add(backendTerminationKey(conn.id, pid));
                    button.closest('tr')?.remove();
                    showToast(`✅ ${data.message}`);
                    refreshActiveSessionsAfterTermination(conn);
                })
                .catch(error => {
                    button.disabled = false;
                    showToast(`❌ ${error.message || 'Не удалось завершить сессию пользователя'}`);
                });
        });
    }

    function refreshActiveSessionsAfterTermination(conn) {
        if (String(activeConnectionId) !== String(conn.id)) return;
        refreshActiveSessionsForConnection(conn, {silent: true});
        [500, 1500].forEach(delay => window.setTimeout(() => {
            if (String(activeConnectionId) === String(conn.id) && document.getElementById('page-sessions')?.classList.contains('active')) {
                refreshActiveSessionsForConnection(conn, {silent: true});
            }
        }, delay));
    }

    function terminateObservedProcess(button, apiUrl, processType, refresh) {
        const pid = processType === 'lock' ? button.dataset.lockPid : button.dataset.transactionPid;
        const conn = connections.find(item => String(item.id) === String(activeConnectionId));
        if (!conn || !/^\d+$/.test(String(conn.id)) || !/^\d+$/.test(String(pid))) return;
        const confirmation = processType === 'lock'
            ? `Завершить процесс блокировки с PID ${pid}?`
            : `Завершить простаивающую транзакцию с PID ${pid}?`;
        requestBackendTermination(button, confirmation, () => {
            button.disabled = true;
            connectionRequest(apiUrl, {id: conn.id, pid: Number(pid)})
                .then(data => {
                    showToast(`✅ ${data.message}`);
                    refresh(conn, {silent: true});
                })
                .catch(error => {
                    button.disabled = false;
                    showToast(`❌ ${error.message || 'Не удалось завершить процесс'}`);
                });
        });
    }

    function refreshActiveSessionsForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId)), options = {}) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderActiveSessionsWarning('Выберите сохранённое подключение для загрузки активных сессий и подключений');
            return;
        }
        syncActiveSessionsFilters();
        const requestId = ++activeSessionsRequestId;
        activeSessionsState.inFlight = true;
        if (!options.silent) renderActiveSessionsWarning('Загрузка активных сессий и подключений...');
        connectionRequest(activeSessionsApiUrl, {id: conn.id, username: activeSessionsState.username, state: activeSessionsState.state})
            .then(data => {
                if (requestId !== activeSessionsRequestId) return;
                renderActiveSessions(data);
            })
            .catch(error => {
                if (requestId !== activeSessionsRequestId) return;
                renderActiveSessionsWarning(error.message || 'Не удалось получить активные сессии и подключения');
            })
            .finally(() => { activeSessionsState.inFlight = false; });
    }

    function syncBlockingLocksUserFilters() {
        const blockedInput = document.getElementById('blockingLocksBlockedUserFilter');
        const blockerInput = document.getElementById('blockingLocksBlockerUserFilter');
        blockingLocksState.blockedUsername = blockedInput ? blockedInput.value.trim() : '';
        blockingLocksState.blockerUsername = blockerInput ? blockerInput.value.trim() : '';
    }

    function getBlockingLocksFilterLabel() {
        const filters = [];
        if (blockingLocksState.blockedUsername) filters.push(`заблок.: ${blockingLocksState.blockedUsername}`);
        if (blockingLocksState.blockerUsername) filters.push(`блок.: ${blockingLocksState.blockerUsername}`);
        return filters.join(', ');
    }

    function renderBlockingLocksWarning(message) {
        const tbody = document.getElementById('blockingLocksTableBody');
        const count = document.getElementById('blockingLocksCount');
        if (count) count.textContent = 'Нет данных';
        if (tbody) tbody.innerHTML = `<tr><td colspan="${canRunDestructiveActions() ? 9 : 8}" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderBlockingLocks(data) {
        const tbody = document.getElementById('blockingLocksTableBody');
        const count = document.getElementById('blockingLocksCount');
        const locks = data.locks || [];
        const filterLabel = getBlockingLocksFilterLabel();
        if (count) count.textContent = filterLabel
            ? `${locks.length} блокировок (${filterLabel})`
            : `${locks.length} блокировок`;
        if (!tbody) return;
        if (!locks.length) {
            tbody.innerHTML = `<tr><td colspan="${canRunDestructiveActions() ? 9 : 8}" class="text-muted">Блокировки не найдены</td></tr>`;
            return;
        }
        tbody.innerHTML = locks.map(lock => `
            <tr>
                <td><span class="text-danger"><strong>${escapeHtml(lock.blocked_pid)}</strong></span></td>
                <td>${escapeHtml(lock.blocked_user)}</td>
                <td>${escapeHtml(lock.blocked_duration)}</td>
                <td style="max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; color:var(--text-muted);" title="${escapeHtml(lock.blocked_query)}">${escapeHtml(lock.blocked_query)}</td>
                <td><span class="text-warning"><strong>${escapeHtml(lock.blocker_pid)}</strong></span></td>
                <td>${escapeHtml(lock.blocker_user)}</td>
                <td>${escapeHtml(lock.blocker_duration)}</td>
                <td style="max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; color:var(--text-muted);" title="${escapeHtml(lock.blocker_query)}">${escapeHtml(lock.blocker_query)}</td>
                ${canRunDestructiveActions() ? `<td class="backend-terminate-actions blocking-lock-actions">
                    <button type="button" class="btn btn-sm btn-outline-danger" data-lock-pid="${escapeHtml(lock.blocked_pid)}" title="Завершить заблокированный процесс PID ${escapeHtml(lock.blocked_pid)}">Завершить заблокированный</button>
                    <button type="button" class="btn btn-sm btn-outline-danger" data-lock-pid="${escapeHtml(lock.blocker_pid)}" title="Завершить блокирующий процесс PID ${escapeHtml(lock.blocker_pid)}">Завершить блокирующий</button>
                </td>` : ''}
            </tr>
        `).join('');
    }

    function scheduleBlockingLocksRefresh() {
        if (blockingLocksState.timer) {
            clearInterval(blockingLocksState.timer);
            blockingLocksState.timer = null;
        }
        if (!blockingLocksState.refreshInterval) return;
        blockingLocksState.timer = setInterval(() => {
            if (!blockingLocksState.inFlight && !document.hidden && document.getElementById('page-locks')?.classList.contains('active')) {
                refreshBlockingLocksForConnection(undefined, {silent: true});
            }
        }, blockingLocksState.refreshInterval * 1000);
    }

    function initBlockingLocksControls() {
        document.getElementById('blockingLocksTableBody')?.addEventListener('click', event => {
            const button = event.target.closest('[data-lock-pid]');
            if (button) terminateObservedProcess(button, terminateLockProcessApiUrl, 'lock', refreshBlockingLocksForConnection);
        });
        document.getElementById('blockingLocksRefreshInterval')?.addEventListener('change', function () {
            blockingLocksState.refreshInterval = Number(this.value) || 0;
            scheduleBlockingLocksRefresh();
            refreshBlockingLocksForConnection(undefined, {silent: true});
        });
        let userFilterTimer;
        document.querySelectorAll('[data-blocking-locks-user-filter]').forEach(input => {
            input.addEventListener('input', function () {
                clearTimeout(userFilterTimer);
                userFilterTimer = setTimeout(() => {
                    syncBlockingLocksUserFilters();
                    refreshBlockingLocksForConnection(undefined, {silent: true});
                }, 350);
            });
        });
        document.getElementById('blockingLocksRefreshBtn')?.addEventListener('click', function () {
            refreshBlockingLocksForConnection(undefined, {silent: false});
        });
    }

    function refreshBlockingLocksForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId)), options = {}) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderBlockingLocksWarning('Выберите сохранённое подключение для загрузки блокировок');
            return;
        }
        syncBlockingLocksUserFilters();
        const requestId = ++blockingLocksRequestId;
        blockingLocksState.inFlight = true;
        if (!options.silent) renderBlockingLocksWarning('Загрузка блокировок...');
        connectionRequest(blockingLocksApiUrl, {
            id: conn.id,
            blocked_username: blockingLocksState.blockedUsername,
            blocker_username: blockingLocksState.blockerUsername
        })
            .then(data => {
                if (requestId !== blockingLocksRequestId) return;
                renderBlockingLocks(data);
            })
            .catch(error => {
                if (requestId !== blockingLocksRequestId) return;
                renderBlockingLocksWarning(error.message || 'Не удалось получить блокировки');
            })
            .finally(() => { blockingLocksState.inFlight = false; });
    }

    function syncIdleTransactionsUserFilter() {
        const input = document.getElementById('idleTransactionsUserFilter');
        idleTransactionsState.username = input ? input.value.trim() : '';
    }

    function renderIdleTransactionsWarning(message) {
        const tbody = document.getElementById('idleTransactionsTableBody');
        const count = document.getElementById('idleTransactionsCount');
        if (count) count.textContent = 'Нет данных';
        if (tbody) tbody.innerHTML = `<tr><td colspan="${canRunDestructiveActions() ? 9 : 8}" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderIdleTransactions(data) {
        const tbody = document.getElementById('idleTransactionsTableBody');
        const count = document.getElementById('idleTransactionsCount');
        const transactions = data.transactions || [];
        if (count) count.textContent = idleTransactionsState.username
            ? `${transactions.length} транзакций для ${idleTransactionsState.username}`
            : `${transactions.length} транзакций`;
        if (!tbody) return;
        if (!transactions.length) {
            tbody.innerHTML = `<tr><td colspan="${canRunDestructiveActions() ? 9 : 8}" class="text-muted">Транзакции не найдены</td></tr>`;
            return;
        }
        tbody.innerHTML = transactions.map(transaction => `
            <tr>
                <td><strong>${escapeHtml(transaction.pid)}</strong></td>
                <td>${escapeHtml(transaction.username)}</td>
                <td>${escapeHtml(transaction.application_name)}</td>
                <td>${escapeHtml(transaction.client_addr)}</td>
                <td><span class="status-badge warning">${escapeHtml(transaction.state)}</span></td>
                <td>${escapeHtml(transaction.transaction_duration)}</td>
                <td>${escapeHtml(transaction.idle_duration)}</td>
                <td style="max-width:360px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; color:var(--text-muted);" title="${escapeHtml(transaction.sql)}">${escapeHtml(transaction.sql)}</td>
                ${canRunDestructiveActions() ? `<td class="backend-terminate-actions"><button type="button" class="btn btn-sm btn-outline-danger" data-transaction-pid="${escapeHtml(transaction.pid)}" title="Завершить транзакцию PID ${escapeHtml(transaction.pid)}">Завершить</button></td>` : ''}
            </tr>
        `).join('');
    }

    function scheduleIdleTransactionsRefresh() {
        if (idleTransactionsState.timer) {
            clearInterval(idleTransactionsState.timer);
            idleTransactionsState.timer = null;
        }
        if (!idleTransactionsState.refreshInterval) return;
        idleTransactionsState.timer = setInterval(() => {
            if (!idleTransactionsState.inFlight && !document.hidden && document.getElementById('page-transactions')?.classList.contains('active')) {
                refreshIdleTransactionsForConnection(undefined, {silent: true});
            }
        }, idleTransactionsState.refreshInterval * 1000);
    }

    function initIdleTransactionsControls() {
        document.getElementById('idleTransactionsTableBody')?.addEventListener('click', event => {
            const button = event.target.closest('[data-transaction-pid]');
            if (button) terminateObservedProcess(button, terminateIdleTransactionApiUrl, 'transaction', refreshIdleTransactionsForConnection);
        });
        document.getElementById('idleTransactionsRefreshInterval')?.addEventListener('change', function () {
            idleTransactionsState.refreshInterval = Number(this.value) || 0;
            scheduleIdleTransactionsRefresh();
            refreshIdleTransactionsForConnection(undefined, {silent: true});
        });
        let userFilterTimer;
        document.getElementById('idleTransactionsUserFilter')?.addEventListener('input', function () {
            clearTimeout(userFilterTimer);
            userFilterTimer = setTimeout(() => {
                idleTransactionsState.username = this.value.trim();
                refreshIdleTransactionsForConnection(undefined, {silent: true});
            }, 350);
        });
        document.getElementById('idleTransactionsRefreshBtn')?.addEventListener('click', function () {
            refreshIdleTransactionsForConnection(undefined, {silent: false});
        });
    }

    function refreshIdleTransactionsForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId)), options = {}) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderIdleTransactionsWarning('Выберите сохранённое подключение для загрузки транзакций');
            return;
        }
        syncIdleTransactionsUserFilter();
        const requestId = ++idleTransactionsRequestId;
        idleTransactionsState.inFlight = true;
        if (!options.silent) renderIdleTransactionsWarning('Загрузка транзакций...');
        connectionRequest(idleTransactionsApiUrl, {id: conn.id, username: idleTransactionsState.username})
            .then(data => {
                if (requestId !== idleTransactionsRequestId) return;
                renderIdleTransactions(data);
            })
            .catch(error => {
                if (requestId !== idleTransactionsRequestId) return;
                renderIdleTransactionsWarning(error.message || 'Не удалось получить транзакции');
            })
            .finally(() => { idleTransactionsState.inFlight = false; });
    }


    function getSizeMetricValue(sizeMetrics, key, field = 'size_bytes') {
        const item = sizeMetrics.find(metric => metric.key === key);
        return item ? item[field] : null;
    }

    function updateMemorySizeMetricsChart(sizeMetrics) {
        const donut = document.getElementById('memorySizeMetricsDonut');
        const summary = document.getElementById('memorySizeMetricsSummary');
        if (!donut || !summary) return;

        const total = Number(getSizeMetricValue(sizeMetrics, 'total')) || 0;
        const dataWithoutIndexes = Math.max(Number(getSizeMetricValue(sizeMetrics, 'data_without_indexes')) || 0, 0);
        const indexes = Math.max(Number(getSizeMetricValue(sizeMetrics, 'indexes')) || 0, 0);
        const totalLabel = getSizeMetricValue(sizeMetrics, 'total', 'value') || '—';
        const dataPercent = total > 0 ? Math.min((dataWithoutIndexes * 100) / total, 100) : 0;
        const indexPercent = total > 0 ? Math.min((indexes * 100) / total, 100 - dataPercent) : 0;
        const dataEnd = dataPercent.toFixed(2);
        const indexEnd = (dataPercent + indexPercent).toFixed(2);
        const gradient = total > 0
            ? `var(--accent-blue) 0 ${dataEnd}%, var(--accent-purple) ${dataEnd}% ${indexEnd}%, #e8eaee ${indexEnd}% 100%`
            : '#e8eaee 0 100%';

        donut.style.setProperty('--size-metrics-gradient', gradient);
        donut.setAttribute('aria-label', `Детализация размеров: данные ${dataPercent.toFixed(2)}%, индексы ${indexPercent.toFixed(2)}%`);
        summary.textContent = totalLabel;
    }

    function renderMemoryOverviewWarning(message) {
        const sizeTbody = document.getElementById('memorySizeMetricsTableBody');
        const settingsTbody = document.getElementById('memorySettingsTableBody');
        const usageList = document.getElementById('memoryUsageList');
        const sizeCount = document.getElementById('memorySizeMetricsCount');
        const settingsCount = document.getElementById('memorySettingsCount');
        const usageCount = document.getElementById('memoryUsageCount');
        if (sizeCount) sizeCount.textContent = 'Нет данных';
        if (settingsCount) settingsCount.textContent = 'Нет данных';
        if (usageCount) usageCount.textContent = 'Нет данных';
        updateMemorySizeMetricsChart([]);
        if (sizeTbody) sizeTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (settingsTbody) settingsTbody.innerHTML = `<tr><td colspan="3" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (usageList) usageList.innerHTML = `<div class="text-muted">${escapeHtml(message)}</div>`;
    }

    function renderMemoryOverview(data) {
        const sizeTbody = document.getElementById('memorySizeMetricsTableBody');
        const settingsTbody = document.getElementById('memorySettingsTableBody');
        const usageList = document.getElementById('memoryUsageList');
        const sizeCount = document.getElementById('memorySizeMetricsCount');
        const settingsCount = document.getElementById('memorySettingsCount');
        const usageCount = document.getElementById('memoryUsageCount');
        const sizeMetrics = data.size_metrics || [];
        const settings = data.settings || [];
        const usage = data.usage || [];
        if (sizeCount) sizeCount.textContent = `${sizeMetrics.length} метрик`;
        if (settingsCount) settingsCount.textContent = `${settings.length} параметров`;
        if (usageCount) usageCount.textContent = `${usage.length} показателя`;
        updateMemorySizeMetricsChart(sizeMetrics);
        if (sizeTbody) {
            if (!sizeMetrics.length) {
                sizeTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Детализация размеров не найдена</td></tr>';
            } else {
                sizeTbody.innerHTML = sizeMetrics.map(item => `
                    <tr>
                        <td>${escapeHtml(item.label)}</td>
                        <td><strong>${escapeHtml(item.value)}</strong></td>
                    </tr>
                `).join('');
            }
        }
        if (settingsTbody) {
            if (!settings.length) {
                settingsTbody.innerHTML = '<tr><td colspan="3" class="text-muted">Параметры памяти не найдены</td></tr>';
            } else {
                settingsTbody.innerHTML = settings.map(item => `
                    <tr>
                        <td><code>${escapeHtml(item.key)}</code></td>
                        <td><strong>${escapeHtml(item.value)}</strong></td>
                        <td>${escapeHtml(item.role)}</td>
                    </tr>
                `).join('');
            }
        }
        if (usageList) {
            if (!usage.length) {
                usageList.innerHTML = '<div class="text-muted">Использование памяти не найдено</div>';
            } else {
                usageList.innerHTML = usage.map(item => {
                    const percent = Math.max(0, Math.min(Number(item.usage_percent) || 0, 100));
                    const barClass = percent >= 85 ? 'danger' : percent >= 70 ? 'warning' : 'success';
                    return `
                    <div class="memory-usage-item">
                        <div class="memory-usage-row">
                            <span class="memory-usage-label">${escapeHtml(item.label)}</span>
                            <span class="memory-usage-value">${escapeHtml(item.used)} / ${escapeHtml(item.limit)}</span>
                        </div>
                        <div class="memory-usage-track">
                            <div class="memory-usage-bar ${barClass}" style="width: ${percent}%;"></div>
                        </div>
                    </div>
                `;
                }).join('');
            }
        }
    }

    function refreshMemoryOverviewForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const requestId = ++memoryOverviewRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderMemoryOverviewWarning('Выберите сохранённое подключение для загрузки памяти');
            return;
        }
        renderMemoryOverviewWarning('Загрузка памяти...');
        connectionRequest(memoryOverviewApiUrl, {id: conn.id})
            .then(data => {
                if (requestId === memoryOverviewRequestId) renderMemoryOverview(data);
            })
            .catch(error => {
                if (requestId === memoryOverviewRequestId) renderMemoryOverviewWarning(error.message || 'Не удалось получить параметры памяти');
            });
    }

    function refreshUsersForConnection(conn) {
        usersPager.refresh(conn);
    }

    function initUsersControls() {
        usersPager.bindControls();
    }

    function refreshGroupsForConnection(conn) {
        groupsPager.refresh(conn);
    }

    function initGroupsControls() {
        groupsPager.bindControls();
    }

    function isRoleEnabled(value) {
        return value === true || String(value).toLowerCase() === 'true' || value === 'Да';
    }

    function updateRoleDonut(donutId, summaryId, enabledCount, totalCount, enabledLabel, disabledLabel) {
        const donut = document.getElementById(donutId);
        const summary = document.getElementById(summaryId);
        const percent = totalCount > 0 ? Math.max(0, Math.min((enabledCount * 100) / totalCount, 100)) : 0;
        if (donut) {
            donut.style.setProperty('--role-yes', `${percent}%`);
            donut.setAttribute('aria-label', `${enabledLabel}: ${enabledCount}, ${disabledLabel}: ${Math.max(totalCount - enabledCount, 0)}`);
        }
        if (summary) summary.textContent = totalCount > 0 ? `${enabledCount} / ${totalCount}` : '—';
    }

    function updateUsersPrivilegeCharts(roles = [], summary = null) {
        const total = Number(summary?.total_count) || roles.length;
        const superuserCount = summary ? Number(summary.superuser_count) || 0 : roles.filter(role => isRoleEnabled(role.superuser)).length;
        const createDbCount = summary ? Number(summary.createdb_count) || 0 : roles.filter(role => isRoleEnabled(role.createdb)).length;
        const replicationCount = summary ? Number(summary.replication_count) || 0 : roles.filter(role => isRoleEnabled(role.replication)).length;
        updateRoleDonut('usersSuperuserDonut', 'usersSuperuserSummary', superuserCount, total, 'Суперпользователи', 'Обычные пользователи');
        updateRoleDonut('usersCreateDbDonut', 'usersCreateDbSummary', createDbCount, total, 'Могут создавать БД', 'Не могут создавать БД');
        updateRoleDonut('usersReplicationDonut', 'usersReplicationSummary', replicationCount, total, 'Могут выполнять репликацию', 'Без права репликации');
    }

    function isPrivilegedRole(role) {
        return ['superuser', 'createdb', 'createrole', 'replication'].some(key => isRoleEnabled(role[key]));
    }

    function updateGroupsPrivilegeCharts(roles = [], summary = null) {
        const total = Number(summary?.total_count) || roles.length;
        const privilegedCount = summary ? Number(summary.privileged_count) || 0 : roles.filter(isPrivilegedRole).length;
        updateRoleDonut('groupsPrivilegedDonut', 'groupsPrivilegedSummary', privilegedCount, total, 'Привилегированные группы', 'Обычные группы');
        renderGroupsMembersBars(roles);
    }

    function renderGroupsMembersBars(roles = []) {
        const container = document.getElementById('groupsMembersBars');
        if (!container) return;
        const topGroups = [...roles]
            .sort((a, b) => (Number(b.member_count) || 0) - (Number(a.member_count) || 0))
            .slice(0, 8);
        const maxMembers = Math.max(...topGroups.map(role => Number(role.member_count) || 0), 0);
        if (!topGroups.length) {
            container.innerHTML = 'Нет данных';
            return;
        }
        container.innerHTML = topGroups.map(role => {
            const memberCount = Number(role.member_count) || 0;
            const width = maxMembers > 0 ? Math.max((memberCount * 100) / maxMembers, 4) : 0;
            return `
                <div class="groups-members-row">
                    <span class="groups-members-name" title="${escapeHtml(role.name)}">${escapeHtml(role.name)}</span>
                    <span class="groups-members-track"><span class="groups-members-bar" style="width: ${width}%;"></span></span>
                    <span class="groups-members-value">${memberCount}</span>
                </div>
            `;
        }).join('');
    }


    function renderRoleRow(role, includeMembersCount = false) {
        return `
            <tr>
                <td class="favorite-column">${favoriteButton(includeMembersCount ? 'group' : 'user', role.name, role.name)}</td>
                <td><strong>${escapeHtml(role.name)}</strong></td>
                <td>${escapeHtml(role.superuser)}</td>
                <td>${escapeHtml(role.createdb)}</td>
                <td>${escapeHtml(role.createrole)}</td>
                <td>${escapeHtml(role.inherit)}</td>
                <td>${escapeHtml(role.replication)}</td>
                <td>${escapeHtml(role.connection_limit)}</td>
                ${includeMembersCount ? `<td>${escapeHtml(role.member_count)}</td>` : ''}
                <td>${escapeHtml(role.valid_until)}</td>
            </tr>
        `;
    }

    function getMaintenanceStatusClass(deadPercent) {
        if (deadPercent > 25) return 'danger';
        if (deadPercent >= 10) return 'warning';
        return 'success';
    }

    function getMaintenanceTableKey(table) {
        return `${table.schema_name}.${table.table_name}`;
    }

    function resetMaintenanceVisuals() {
        const heatmap = document.getElementById('maintenanceStatusHeatmap');
        const donut = document.getElementById('maintenanceRowsDonut');
        const donutSummary = document.getElementById('maintenanceRowsDonutSummary');
        const donutTable = document.getElementById('maintenanceRowsDonutTable');
        if (heatmap) heatmap.textContent = 'Нет данных';
        if (donut) donut.style.setProperty('--maintenance-live-dead', '#e8eaee 0 100%');
        if (donutSummary) donutSummary.textContent = '—';
        if (donutTable) donutTable.textContent = 'Выберите таблицу';
    }

    function updateMaintenanceRowsDonut(table) {
        const donut = document.getElementById('maintenanceRowsDonut');
        const summary = document.getElementById('maintenanceRowsDonutSummary');
        const tableLabel = document.getElementById('maintenanceRowsDonutTable');
        if (!donut || !summary || !tableLabel) return;
        if (!table) {
            donut.style.setProperty('--maintenance-live-dead', '#e8eaee 0 100%');
            summary.textContent = '—';
            tableLabel.textContent = 'Выберите таблицу';
            return;
        }
        const liveRows = Number(table.live_rows) || 0;
        const deadRows = Number(table.dead_rows) || 0;
        const totalRows = liveRows + deadRows;
        const livePercent = totalRows > 0 ? (liveRows * 100) / totalRows : 0;
        donut.style.setProperty('--maintenance-live-dead', totalRows > 0
            ? `var(--accent-green) 0 ${livePercent.toFixed(2)}%, var(--accent-red) ${livePercent.toFixed(2)}% 100%`
            : '#e8eaee 0 100%');
        donut.setAttribute('aria-label', `Живых строк ${formatRowCount(liveRows)}, мёртвых строк ${formatRowCount(deadRows)}`);
        summary.textContent = `${formatRowCount(liveRows)} / ${formatRowCount(deadRows)}`;
        tableLabel.textContent = getMaintenanceTableKey(table);
    }

    function renderMaintenanceHeatmap(tables) {
        const container = document.getElementById('maintenanceStatusHeatmap');
        if (!container) return;
        const heatmapTables = [...tables]
            .sort((a, b) => (Number(b.dead_percent) || 0) - (Number(a.dead_percent) || 0))
            .slice(0, 20);
        if (!heatmapTables.length) {
            container.textContent = 'Нет данных';
            return;
        }
        container.innerHTML = heatmapTables.map(table => {
            const deadPercent = Number(table.dead_percent) || 0;
            const statusClass = getMaintenanceStatusClass(deadPercent);
            const tableName = getMaintenanceTableKey(table);
            return `
                <div class="maintenance-heatmap-cell ${statusClass}" title="${escapeHtml(tableName)}: ${deadPercent}%">
                    <span>${escapeHtml(table.table_name)}</span>
                    <small>${deadPercent}%</small>
                </div>
            `;
        }).join('');
    }

    function updateMaintenanceVisuals(tables) {
        if (!tables.length) {
            resetMaintenanceVisuals();
            return;
        }
        renderMaintenanceHeatmap(tables);
        if (!maintenanceStatsState.selectedTableKey || !tables.some(table => getMaintenanceTableKey(table) === maintenanceStatsState.selectedTableKey)) {
            maintenanceStatsState.selectedTableKey = getMaintenanceTableKey(tables[0]);
        }
        updateMaintenanceRowsDonut(tables.find(table => getMaintenanceTableKey(table) === maintenanceStatsState.selectedTableKey));
    }

    function renderMaintenanceStatsWarning(message) {
        const tbody = document.getElementById('maintenanceStatsTableBody');
        const count = document.getElementById('maintenanceStatsCount');
        const info = document.getElementById('maintenancePageInfo');
        maintenanceStatsState.totalCount = 0;
        maintenanceStatsState.selectedTableKey = '';
        resetMaintenanceVisuals();
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1';
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-muted">${escapeHtml(message)}</td></tr>`;
        updatePaginationButtons(maintenanceStatsState, 'maintenancePrevPageBtn', 'maintenanceNextPageBtn');
    }

    function updateMaintenanceSortIndicators() {
        document.querySelectorAll('[data-maintenance-sort]').forEach(button => {
            const isActive = button.dataset.maintenanceSort === maintenanceStatsState.sort;
            button.classList.toggle('active', isActive);
            updateSortHeaderState(button, isActive, maintenanceStatsState.direction);
        });
    }

    function renderMaintenanceStats(data) {
        const tbody = document.getElementById('maintenanceStatsTableBody');
        const count = document.getElementById('maintenanceStatsCount');
        const info = document.getElementById('maintenancePageInfo');
        const tables = data.tables || [];
        maintenanceStatsState.totalCount = Number(data.total_count) || 0;
        maintenanceStatsState.page = Number(data.page) || 1;
        maintenanceStatsState.pageSize = Number(data.page_size) || defaultPaginationPageSize;
        const totalPages = Math.max(Math.ceil(maintenanceStatsState.totalCount / maintenanceStatsState.pageSize), 1);
        if (count) count.textContent = `${tables.length} из ${maintenanceStatsState.totalCount} таблиц`;
        if (info) info.textContent = `Страница ${maintenanceStatsState.page} из ${totalPages}`;
        updateMaintenanceSortIndicators();
        updatePaginationButtons(maintenanceStatsState, 'maintenancePrevPageBtn', 'maintenanceNextPageBtn');
        updateMaintenanceVisuals(tables);
        if (!tbody) return;
        if (!tables.length) {
            tbody.innerHTML = `<tr><td colspan="${canRunDestructiveActions() ? 8 : 7}" class="text-muted">Статистика обслуживания не найдена</td></tr>`;
            return;
        }
        tbody.innerHTML = tables.map(table => {
            const deadPercent = Number(table.dead_percent) || 0;
            const deadClass = deadPercent >= 10 ? 'text-danger' : (deadPercent >= 1 ? 'text-warning' : 'text-success');
            const tableKey = getMaintenanceTableKey(table);
            const activeClass = tableKey === maintenanceStatsState.selectedTableKey ? ' active' : '';
            const runningJob = Array.from(maintenanceJobs.values()).find(job => job.tableKey === tableKey && ['queued', 'running'].includes(job.status));
            return `
                <tr class="maintenance-row-selectable${activeClass}" data-maintenance-table-key="${escapeHtml(tableKey)}">
                    <td>${escapeHtml(table.schema_name)}</td>
                    <td><code>${escapeHtml(table.table_name)}</code></td>
                    <td>${formatRowCount(table.live_rows)}</td>
                    <td>${formatRowCount(table.dead_rows)}</td>
                    <td><span class="${deadClass}">${deadPercent}%</span></td>
                    <td>${escapeHtml(table.last_vacuum)}</td>
                    <td>${escapeHtml(table.last_analyze)}</td>
                    ${canRunDestructiveActions() ? `<td class="maintenance-actions">
                        <button class="btn btn-sm btn-outline-primary" type="button" data-maintenance-operation="vacuum" data-schema-name="${escapeHtml(table.schema_name)}" data-table-name="${escapeHtml(table.table_name)}" ${runningJob ? 'disabled' : ''}>VACUUM</button>
                        <button class="btn btn-sm btn-outline-danger" type="button" data-maintenance-operation="vacuum_full" data-schema-name="${escapeHtml(table.schema_name)}" data-table-name="${escapeHtml(table.table_name)}" ${runningJob ? 'disabled' : ''}>VACUUM FULL</button>
                        <button class="btn btn-sm btn-outline-success" type="button" data-maintenance-operation="analyze" data-schema-name="${escapeHtml(table.schema_name)}" data-table-name="${escapeHtml(table.table_name)}" ${runningJob ? 'disabled' : ''}>ANALYZE</button>
                        <button class="btn btn-sm btn-outline-info" type="button" data-maintenance-operation="explain_analyze" data-schema-name="${escapeHtml(table.schema_name)}" data-table-name="${escapeHtml(table.table_name)}" ${runningJob ? 'disabled' : ''}>EXPLAIN ANALYZE</button>
                        ${runningJob ? `<span class="maintenance-job-running"><i class="fas fa-spinner fa-spin" aria-hidden="true"></i> ${runningJob.status === 'queued' ? 'В очереди' : 'Выполняется'}</span>` : ''}
                    </td>` : ''}
                </tr>
            `;
        }).join('');
        tbody.querySelectorAll('[data-maintenance-table-key]').forEach(row => {
            row.addEventListener('click', function () {
                maintenanceStatsState.selectedTableKey = this.dataset.maintenanceTableKey;
                updateMaintenanceRowsDonut(tables.find(table => getMaintenanceTableKey(table) === maintenanceStatsState.selectedTableKey));
                tbody.querySelectorAll('.maintenance-row-selectable').forEach(item => item.classList.remove('active'));
                this.classList.add('active');
            });
        });
        tbody.querySelectorAll('[data-maintenance-operation]').forEach(button => {
            button.addEventListener('click', function (event) {
                event.stopPropagation();
                startMaintenanceOperation(this.dataset.schemaName, this.dataset.tableName, this.dataset.maintenanceOperation);
            });
        });
    }

    function getMaintenanceOperationLabel(operation) {
        return {
            vacuum: 'VACUUM',
            vacuum_full: 'VACUUM FULL',
            analyze: 'ANALYZE',
            explain_analyze: 'EXPLAIN ANALYZE'
        }[operation] || String(operation || '').toUpperCase();
    }

    function renderBackgroundJobs(jobs = []) {
        const indicator = document.getElementById('backgroundJobsIndicator');
        const count = document.getElementById('backgroundJobsCount');
        const list = document.getElementById('backgroundJobsList');
        const clearAllButton = document.getElementById('backgroundJobsClearAllBtn');
        const activeJobs = jobs.filter(job => ['queued', 'running'].includes(job.status));
        const visibleJobs = jobs.filter(job => !dismissedBackgroundJobIds.has(String(job.id)));
        const dismissibleJobs = visibleJobs.filter(job => !['queued', 'running'].includes(job.status));
        if (count) count.textContent = String(activeJobs.length);
        indicator?.classList.toggle('has-active-jobs', activeJobs.length > 0);
        if (clearAllButton) clearAllButton.disabled = dismissibleJobs.length === 0;
        if (!list) return;
        if (!visibleJobs.length) {
            list.textContent = 'Нет фоновых операций';
            return;
        }
        const formatJobDateTime = value => {
            if (!value) return '—';
            const parsed = new Date(value);
            return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
        };
        list.innerHTML = visibleJobs.slice(0, 8).map(job => {
            const labels = {queued: 'В очереди', running: 'Выполняется', completed: 'Завершено', failed: 'Ошибка'};
            const clearButton = ['queued', 'running'].includes(job.status) ? '' : `<button class="background-job-clear" type="button" data-background-job-clear="${escapeHtml(job.id)}" title="Очистить операцию" aria-label="Очистить операцию"><i class="fas fa-times" aria-hidden="true"></i></button>`;
            if (job.kind === 'report') {
                const download = job.download_url ? `<a class="background-job-download" href="${escapeHtml(job.download_url)}"><i class="fas fa-download"></i> Отчет PDF</a>` : '';
                return `<div class="background-job-item">
                    ${clearButton}
                    <b>PDF-отчёт</b>
                    <small>${escapeHtml(job.connection_name)} · ${escapeHtml(labels[job.status] || job.status)}</small>
                    <small><span class="background-job-user-label">Пользователь:</span> ${escapeHtml(job.username || '—')}</small>
                    <dl class="background-job-times">
                        <div><dt>Начало</dt><dd>${escapeHtml(formatJobDateTime(job.started))}</dd></div>
                        <div><dt>Окончание</dt><dd>${escapeHtml(formatJobDateTime(job.finished))}</dd></div>
                    </dl>${download}
                </div>`;
            }
            return `<div class="background-job-item">
                ${clearButton}
                <b>${escapeHtml(getMaintenanceOperationLabel(job.operation))}</b> · ${escapeHtml(job.schema_name)}.${escapeHtml(job.table_name)}
                <small>${escapeHtml(job.connection_name)} · ${escapeHtml(labels[job.status] || job.status)}</small>
                <small><span class="background-job-user-label">Пользователь:</span> ${escapeHtml(job.username || '—')}</small>
                <dl class="background-job-times">
                    <div><dt>Начало</dt><dd>${escapeHtml(formatJobDateTime(job.started))}</dd></div>
                    <div><dt>Окончание</dt><dd>${escapeHtml(formatJobDateTime(job.finished))}</dd></div>
                </dl>
            </div>`;
        }).join('');
    }

    function loadBackgroundJobs() {
        if (document.hidden) return;
        connectionRequest(maintenanceJobsApiUrl, {}).then(data => {
            backgroundJobsErrorNotified = false;
            const jobs = data.jobs || [];
            latestBackgroundJobs = jobs;
            renderBackgroundJobs(jobs);
            jobs.filter(job => ['queued', 'running'].includes(job.status)).forEach(job => {
                if (job.kind === 'report') return;
                if (maintenanceJobs.has(job.id)) return;
                maintenanceJobs.set(job.id, {...job, tableKey: `${job.schema_name}.${job.table_name}`});
                pollMaintenanceJob(job.id);
            });
        }).catch(error => {
            renderBackgroundJobs([]);
            // This poll runs every 10s — only notify once per failure streak so a
            // dropped session/network blip doesn't spam a toast on every tick.
            if (!backgroundJobsErrorNotified) {
                backgroundJobsErrorNotified = true;
                showToast(`❌ ${error.message || 'Не удалось обновить список фоновых операций'}`);
            }
        });
    }

    function initBackgroundJobs() {
        const indicator = document.getElementById('backgroundJobsIndicator');
        const panel = document.getElementById('backgroundJobsPanel');
        const list = document.getElementById('backgroundJobsList');
        const clearAllButton = document.getElementById('backgroundJobsClearAllBtn');
        const saveDismissedJobs = () => {
            localStorage.setItem(dismissedBackgroundJobsStorageKey, Array.from(dismissedBackgroundJobIds).slice(-100).join(','));
        };
        indicator?.addEventListener('click', event => {
            event.stopPropagation();
            const open = panel?.hasAttribute('hidden');
            if (open) panel.removeAttribute('hidden'); else panel?.setAttribute('hidden', '');
            indicator.setAttribute('aria-expanded', String(open));
            if (open) loadBackgroundJobs();
        });
        panel?.addEventListener('click', event => event.stopPropagation());
        list?.addEventListener('click', event => {
            const button = event.target.closest('[data-background-job-clear]');
            if (!button) return;
            dismissedBackgroundJobIds.add(button.dataset.backgroundJobClear);
            saveDismissedJobs();
            renderBackgroundJobs(latestBackgroundJobs);
        });
        clearAllButton?.addEventListener('click', () => {
            latestBackgroundJobs.filter(job => !['queued', 'running'].includes(job.status)).forEach(job => dismissedBackgroundJobIds.add(String(job.id)));
            saveDismissedJobs();
            renderBackgroundJobs(latestBackgroundJobs);
        });
        document.addEventListener('click', () => {
            panel?.setAttribute('hidden', '');
            indicator?.setAttribute('aria-expanded', 'false');
        });
        loadBackgroundJobs();
        window.setInterval(loadBackgroundJobs, 10000);
    }

    function showMaintenanceResult(job) {
        const modalElement = document.getElementById('maintenanceResultModal');
        if (!modalElement) return;
        const succeeded = job.status === 'completed';
        document.getElementById('maintenanceResultOperation').textContent = getMaintenanceOperationLabel(job.operation);
        document.getElementById('maintenanceResultTable').textContent = `${job.schema_name}.${job.table_name}`;
        document.getElementById('maintenanceResultStatus').innerHTML = succeeded
            ? '<span class="badge bg-success">Успешно завершено</span>'
            : '<span class="badge bg-danger">Ошибка</span>';
        document.getElementById('maintenanceResultDuration').textContent = `${Number(job.duration_seconds || 0).toLocaleString()} с`;
        const message = document.getElementById('maintenanceResultMessage');
        message.textContent = job.message || (succeeded ? 'Операция успешно завершена' : 'Операция завершилась с ошибкой');
        message.className = `alert ${succeeded ? 'alert-success' : 'alert-danger'} mb-3`;
        const statisticsSection = document.getElementById('maintenanceResultStatisticsSection');
        const statistics = job.statistics;
        statisticsSection.classList.toggle('d-none', !statistics);
        if (statistics) {
            document.getElementById('maintenanceResultLiveRows').textContent = formatRowCount(statistics.live_rows);
            document.getElementById('maintenanceResultDeadRows').textContent = formatRowCount(statistics.dead_rows);
        }
        const planSection = document.getElementById('maintenanceExplainPlanSection');
        const plan = document.getElementById('maintenanceExplainPlan');
        const planLines = Array.isArray(job.details) ? job.details : [];
        plan.textContent = planLines.join('\n');
        planSection.classList.toggle('d-none', job.operation !== 'explain_analyze' || planLines.length === 0);
        bootstrap.Modal.getOrCreateInstance(modalElement).show();
    }

    function pollMaintenanceJob(jobId) {
        window.setTimeout(() => {
            connectionRequest(maintenanceOperationApiUrl, {job_id: jobId})
                .then(data => {
                    const job = data.job;
                    const trackedJob = maintenanceJobs.get(jobId);
                    if (!trackedJob) return;
                    trackedJob.status = job.status;
                    if (['queued', 'running'].includes(job.status)) {
                        loadBackgroundJobs();
                        pollMaintenanceJob(jobId);
                        return;
                    }
                    maintenanceJobs.delete(jobId);
                    const operationLabel = getMaintenanceOperationLabel(job.operation);
                    const tableLabel = `${job.schema_name}.${job.table_name}`;
                    if (job.status === 'completed') {
                        showToast(`✅ ${operationLabel} для ${tableLabel} завершён`);
                        refreshMaintenanceStatsForConnection();
                    } else {
                        const failureMessage = translateInterfaceText(job.message || 'операция завершилась с ошибкой');
                        showToast(`❌ ${operationLabel} для ${tableLabel}: ${failureMessage}`);
                    }
                    showMaintenanceResult(job);
                    loadBackgroundJobs();
                })
                .catch(error => {
                    maintenanceJobs.delete(jobId);
                    showToast(`❌ Не удалось получить статус обслуживания: ${error.message}`);
                    refreshMaintenanceStatsForConnection();
                });
        }, 1500);
    }

    function startMaintenanceOperation(schemaName, tableName, operation) {
        const conn = connections.find(c => String(c.id) === String(activeConnectionId));
        if (!conn) {
            showToast('⚠️ Выберите подключение');
            return;
        }
        const tableKey = `${schemaName}.${tableName}`;
        connectionRequest(maintenanceOperationApiUrl, {
            id: conn.id,
            schema_name: schemaName,
            table_name: tableName,
            operation
        })
            .then(data => {
                maintenanceJobs.set(data.job.id, {...data.job, tableKey});
                showToast(`⏳ ${getMaintenanceOperationLabel(operation)} для ${tableKey} запущен в фоне`);
                refreshMaintenanceStatsForConnection();
                pollMaintenanceJob(data.job.id);
                loadBackgroundJobs();
            })
            .catch(error => showToast(`❌ Не удалось запустить обслуживание: ${error.message}`));
    }

    function refreshMaintenanceStatsForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderMaintenanceStatsWarning('Выберите сохранённое подключение для загрузки статистики обслуживания');
            return;
        }
        const requestId = ++maintenanceStatsRequestId;
        renderMaintenanceStatsWarning('Загрузка статистики обслуживания...');
        connectionRequest(maintenanceStatsApiUrl, {
            id: conn.id,
            page: maintenanceStatsState.page,
            page_size: maintenanceStatsState.pageSize,
            search: maintenanceStatsState.search,
            sort: maintenanceStatsState.sort,
            direction: maintenanceStatsState.direction
        })
            .then(data => {
                if (requestId === maintenanceStatsRequestId) renderMaintenanceStats(data);
            })
            .catch(error => {
                if (requestId === maintenanceStatsRequestId) renderMaintenanceStatsWarning(error.message || 'Не удалось получить статистику обслуживания');
            });
    }

    function initMaintenanceStatsControls() {
        let searchTimer = null;
        document.getElementById('maintenanceSearchInput')?.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                maintenanceStatsState.search = this.value.trim();
                maintenanceStatsState.page = 1;
                refreshMaintenanceStatsForConnection();
            }, 300);
        });
        document.querySelectorAll('[data-maintenance-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.maintenanceSort;
                if (maintenanceStatsState.sort === sort) {
                    maintenanceStatsState.direction = maintenanceStatsState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    maintenanceStatsState.sort = sort;
                    maintenanceStatsState.direction = ['live_rows', 'dead_rows', 'dead_percent', 'last_vacuum', 'last_analyze'].includes(sort) ? 'desc' : 'asc';
                }
                maintenanceStatsState.page = 1;
                refreshMaintenanceStatsForConnection();
            });
        });
        document.getElementById('maintenancePrevPageBtn')?.addEventListener('click', function () {
            if (maintenanceStatsState.page > 1) {
                maintenanceStatsState.page -= 1;
                refreshMaintenanceStatsForConnection();
            }
        });
        document.getElementById('maintenanceNextPageBtn')?.addEventListener('click', function () {
            const totalPages = Math.max(Math.ceil(maintenanceStatsState.totalCount / maintenanceStatsState.pageSize), 1);
            if (maintenanceStatsState.page < totalPages) {
                maintenanceStatsState.page += 1;
                refreshMaintenanceStatsForConnection();
            }
        });
    }


    function updateSchemaDistributionChart(schemas = []) {
        const donut = document.getElementById('schemaDistributionDonut');
        const summary = document.getElementById('schemaDistributionSummary');
        const legend = document.getElementById('schemaDistributionLegend');
        if (!donut || !summary || !legend) return;

        const colors = ['#4f8cff', '#8b5cf6', '#22c55e', '#f59e0b', '#06b6d4', '#ec4899', '#f97316', '#ef4444', '#8a9bb0'];
        const normalized = schemas
            .map(schema => ({
                name: schema.schema_name || '—',
                sizeBytes: Number(schema.size_bytes) || 0,
                tableSize: schema.table_size || `${formatDatabaseSize(schema.size_bytes).value} ${formatDatabaseSize(schema.size_bytes).unit}`
            }))
            .filter(schema => schema.sizeBytes > 0);
        const totalBytes = normalized.reduce((sum, schema) => sum + schema.sizeBytes, 0);

        if (!normalized.length || totalBytes <= 0) {
            donut.style.setProperty('--schema-distribution-gradient', '#e8eaee 0 100%');
            donut.setAttribute('aria-label', 'Нет данных о распределении данных по схемам');
            summary.textContent = '—';
            legend.textContent = 'Нет данных';
            return;
        }

        const topSchemas = normalized.slice(0, 8);
        const otherBytes = normalized.slice(8).reduce((sum, schema) => sum + schema.sizeBytes, 0);
        const chartItems = otherBytes > 0
            ? [...topSchemas, {name: 'Остальные', sizeBytes: otherBytes, tableSize: `${formatDatabaseSize(otherBytes).value} ${formatDatabaseSize(otherBytes).unit}`}]
            : topSchemas;
        let cursor = 0;
        const gradient = chartItems.map((schema, index) => {
            const start = cursor;
            const percent = (schema.sizeBytes * 100) / totalBytes;
            cursor += percent;
            return `${colors[index % colors.length]} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
        }).join(', ');
        const totalFormatted = formatDatabaseSize(totalBytes);

        donut.style.setProperty('--schema-distribution-gradient', gradient);
        donut.setAttribute('aria-label', `Распределение данных по схемам, всего ${totalFormatted.value} ${totalFormatted.unit}`);
        summary.textContent = `${totalFormatted.value} ${totalFormatted.unit}`;
        legend.innerHTML = chartItems.map((schema, index) => {
            const percent = ((schema.sizeBytes * 100) / totalBytes).toFixed(1);
            return `
                <div class="schema-distribution-legend-item" title="${escapeHtml(schema.name)}: ${escapeHtml(schema.tableSize)} (${percent}%)">
                    <span class="schema-distribution-legend-dot" style="background:${colors[index % colors.length]};"></span>
                    <span class="schema-distribution-legend-name">${escapeHtml(schema.name)}</span>
                    <span class="schema-distribution-legend-value">${percent}%</span>
                </div>
            `;
        }).join('');
    }

    function refreshSchemaSizesForConnection(conn) {
        schemaSizesPager.refresh(conn);
    }

    function initSchemaSizesControls() {
        schemaSizesPager.bindControls();
    }

    function formatRowCount(value) {
        const number = Number(value) || 0;
        return new Intl.NumberFormat('ru-RU').format(number);
    }


    function updateTableDistributionChart(tables = []) {
        const donut = document.getElementById('tableDistributionDonut');
        const summary = document.getElementById('tableDistributionSummary');
        const legend = document.getElementById('tableDistributionLegend');
        if (!donut || !summary || !legend) return;

        const colors = ['#4f8cff', '#8b5cf6', '#22c55e', '#f59e0b', '#06b6d4', '#ec4899', '#f97316', '#ef4444', '#8a9bb0'];
        const normalized = tables
            .map(table => {
                const tableName = table.table_name || '—';
                const schemaName = table.schema_name || '—';
                return {
                    name: `${schemaName}.${tableName}`,
                    sizeBytes: Number(table.size_bytes) || 0,
                    tableSize: table.table_size || `${formatDatabaseSize(table.size_bytes).value} ${formatDatabaseSize(table.size_bytes).unit}`
                };
            })
            .filter(table => table.sizeBytes > 0);
        const totalBytes = normalized.reduce((sum, table) => sum + table.sizeBytes, 0);

        if (!normalized.length || totalBytes <= 0) {
            donut.style.setProperty('--schema-distribution-gradient', '#e8eaee 0 100%');
            donut.setAttribute('aria-label', 'Нет данных о распределении данных по таблицам');
            summary.textContent = '—';
            legend.textContent = 'Нет данных';
            return;
        }

        const topTables = normalized.slice(0, 8);
        const otherBytes = normalized.slice(8).reduce((sum, table) => sum + table.sizeBytes, 0);
        const chartItems = otherBytes > 0
            ? [...topTables, {name: 'Остальные', sizeBytes: otherBytes, tableSize: `${formatDatabaseSize(otherBytes).value} ${formatDatabaseSize(otherBytes).unit}`}]
            : topTables;
        let cursor = 0;
        const gradient = chartItems.map((table, index) => {
            const start = cursor;
            const percent = (table.sizeBytes * 100) / totalBytes;
            cursor += percent;
            return `${colors[index % colors.length]} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
        }).join(', ');
        const totalFormatted = formatDatabaseSize(totalBytes);

        donut.style.setProperty('--schema-distribution-gradient', gradient);
        donut.setAttribute('aria-label', `Распределение данных по таблицам, всего ${totalFormatted.value} ${totalFormatted.unit}`);
        summary.textContent = `${totalFormatted.value} ${totalFormatted.unit}`;
        legend.innerHTML = chartItems.map((table, index) => {
            const percent = ((table.sizeBytes * 100) / totalBytes).toFixed(1);
            return `
                <div class="schema-distribution-legend-item" title="${escapeHtml(table.name)}: ${escapeHtml(table.tableSize)} (${percent}%)">
                    <span class="schema-distribution-legend-dot" style="background:${colors[index % colors.length]};"></span>
                    <span class="schema-distribution-legend-name">${escapeHtml(table.name)}</span>
                    <span class="schema-distribution-legend-value">${percent}%</span>
                </div>
            `;
        }).join('');
    }
    function refreshTableSizesForConnection(conn) {
        tableSizesPager.refresh(conn);
    }

    function initTableSizesControls() {
        tableSizesPager.bindControls();
    }

    function updateViewsSummaryChart(summary = null, views = []) {
        const donut = document.getElementById('viewsTypeDonut');
        const typeSummary = document.getElementById('viewsTypeSummary');
        const sizeSummary = document.getElementById('viewsMaterializedSizeSummary');
        if (!donut || !typeSummary || !sizeSummary) return;

        const materializedCount = Number(summary?.materialized_count ?? views.filter(view => view.view_type === 'Материализованное').length) || 0;
        const ordinaryCount = Number(summary?.ordinary_count ?? views.filter(view => view.view_type === 'Обычное').length) || 0;
        const total = materializedCount + ordinaryCount;
        const materializedPercent = total > 0 ? Math.round((materializedCount / total) * 100) : 0;
        const materializedSizeBytes = Number(summary?.materialized_size_bytes ?? views.reduce((acc, view) => acc + (Number(view.size_bytes) || 0), 0)) || 0;
        const formattedSize = summary?.materialized_size || `${formatDatabaseSize(materializedSizeBytes).value} ${formatDatabaseSize(materializedSizeBytes).unit}`;

        donut.style.setProperty('--role-yes', `${materializedPercent}%`);
        donut.setAttribute('aria-label', `Материализованные представления: ${materializedCount}, обычные представления: ${ordinaryCount}`);
        typeSummary.textContent = total > 0 ? `${materializedCount} / ${ordinaryCount}` : 'Нет данных';
        sizeSummary.textContent = total > 0 || materializedSizeBytes > 0 ? formattedSize : '—';
    }

    function refreshViewsForConnection(conn) {
        viewsPager.refresh(conn);
    }

    function initViewsControls() {
        viewsPager.bindControls();
    }

    function refreshFunctionsForConnection(conn) {
        functionsPager.refresh(conn);
    }

    function initFunctionsControls() {
        functionsPager.bindControls();
    }

    function renderDistributionWarning(message) {
        currentDistributionSegments = [];
        currentDistributionTotalRows = 0;
        const tbody = document.getElementById('distributionTableBody');
        const count = document.getElementById('distributionRowsCount');
        const tableName = document.getElementById('distributionSelectedTableName');
        if (count) count.textContent = 'Нет данных';
        if (tableName) tableName.textContent = 'Выберите таблицу';
        if (tbody) tbody.innerHTML = `<tr><td colspan="3" class="text-muted">${escapeHtml(message)}</td></tr>`;
        updateDistributionMetrics();
        updateSegmentDistributionChart([]);
    }

    function updateDistributionMetrics(metrics = {}) {
        const usedSegments = document.getElementById('distributionUsedSegments');
        const ratio = document.getElementById('distributionSkewRatio');
        const total = document.getElementById('distributionTotalRows');
        const status = document.getElementById('distributionStatus');
        if (usedSegments) usedSegments.textContent = metrics.used_segments ?? '—';
        if (ratio) ratio.textContent = metrics.skew_ratio ?? '—';
        if (total) total.textContent = metrics.total_rows != null ? formatRowCount(metrics.total_rows) : '—';
        if (status) status.textContent = metrics.status || '—';
    }

    function updateSegmentDistributionChart(segments) {
        if (!charts.segmentDist) return;
        const counts = segments.map(item => Number(item.row_count) || 0);
        const maxRows = counts.length ? Math.max(...counts) : 0;
        const minRows = counts.filter(value => value > 0).length ? Math.min(...counts.filter(value => value > 0)) : 0;
        charts.segmentDist.data.labels = segments.map(item => `sg${item.segment_id}`);
        charts.segmentDist.data.datasets[0].data = counts;
        charts.segmentDist.data.datasets[0].backgroundColor = counts.map(value => value === maxRows && maxRows > 0 ? '#ef4444' : value === minRows && minRows > 0 ? '#10b981' : '#4f8cff');
        charts.segmentDist.update();
    }

    function updateDistributionSortIndicators() {
        document.querySelectorAll('[data-distribution-sort]').forEach(button => {
            const isActive = button.dataset.distributionSort === distributionSortState.column;
            button.classList.toggle('active', isActive);
            updateSortHeaderState(button, isActive, distributionSortState.direction);
        });
    }

    function distributionSortValue(item, column) {
        if (column === 'share') {
            return currentDistributionTotalRows ? ((Number(item.row_count) || 0) / currentDistributionTotalRows) * 100 : 0;
        }
        if (column === 'row_count') return Number(item.row_count) || 0;
        return Number(item.segment_id) || 0;
    }

    function renderDistributionRows() {
        const tbody = document.getElementById('distributionTableBody');
        if (!tbody) return;
        updateDistributionSortIndicators();
        if (!currentDistributionSegments.length) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-muted">Нет данных о распределении строк</td></tr>';
            return;
        }
        const multiplier = distributionSortState.direction === 'asc' ? 1 : -1;
        const rows = [...currentDistributionSegments].sort((left, right) => {
            return (distributionSortValue(left, distributionSortState.column) - distributionSortValue(right, distributionSortState.column)) * multiplier;
        });
        tbody.innerHTML = rows.map(item => {
            const rowsCount = Number(item.row_count) || 0;
            const share = currentDistributionTotalRows ? ((rowsCount / currentDistributionTotalRows) * 100).toFixed(2) : '0.00';
            return `
                <tr>
                    <td><strong>sg${item.segment_id}</strong></td>
                    <td>${formatRowCount(rowsCount)}</td>
                    <td>${share}%</td>
                </tr>
            `;
        }).join('');
    }

    function renderDistributionInfo(data) {
        const count = document.getElementById('distributionRowsCount');
        const tableName = document.getElementById('distributionSelectedTableName');
        currentDistributionSegments = data.segments || [];
        currentDistributionTotalRows = Number(data.metrics?.total_rows) || 0;
        if (tableName) tableName.textContent = `${data.schema_name}.${data.table_name}`;
        if (count) count.textContent = `${currentDistributionSegments.length} сегментов`;
        updateDistributionMetrics(data.metrics || {});
        updateSegmentDistributionChart(currentDistributionSegments);
        renderDistributionRows();
    }

    function distributionTableOptionLabel(table) {
        return `${table.schema_name}.${table.table_name}`;
    }

    function closeDistributionTablePicker() {
        const picker = document.getElementById('distributionTablePicker');
        const select = document.getElementById('distributionTableSelect');
        const options = document.getElementById('distributionTableOptions');
        if (options) options.hidden = true;
        if (select) select.setAttribute('aria-expanded', 'false');
        picker?.classList.remove('is-open');
        distributionPickerActiveIndex = -1;
    }

    function filteredDistributionTables(query = '') {
        const normalizedQuery = query.trim().toLocaleLowerCase();
        if (!normalizedQuery) return distributionTables;
        return distributionTables.filter(table => {
            const label = distributionTableOptionLabel(table).toLocaleLowerCase();
            return label.includes(normalizedQuery)
                || (table.schema_name || '').toLocaleLowerCase().includes(normalizedQuery)
                || (table.table_name || '').toLocaleLowerCase().includes(normalizedQuery);
        });
    }

    function openDistributionTablePicker(query = '') {
        const picker = document.getElementById('distributionTablePicker');
        const select = document.getElementById('distributionTableSelect');
        const options = document.getElementById('distributionTableOptions');
        if (!distributionTables.length || !select || !options) return;
        renderDistributionPickerOptions(filteredDistributionTables(query));
        options.hidden = false;
        select.setAttribute('aria-expanded', 'true');
        picker?.classList.add('is-open');
    }

    function renderDistributionPickerOptions(tables) {
        const options = document.getElementById('distributionTableOptions');
        if (!options) return;
        distributionPickerActiveIndex = -1;
        if (!tables.length) {
            options.innerHTML = '<div class="distribution-table-options-empty">Таблицы не найдены</div>';
            return;
        }
        options.innerHTML = tables.map((table, index) => {
            const label = distributionTableOptionLabel(table);
            const isSelected = selectedDistributionTable && distributionTableOptionLabel(selectedDistributionTable) === label;
            return `<button class="distribution-table-option${isSelected ? ' is-selected' : ''}" type="button" role="option" aria-selected="${isSelected}" data-distribution-option-index="${index}" data-table-label="${escapeHtml(label)}">
                <span class="distribution-table-option-name" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
                <span class="distribution-table-option-type">${escapeHtml(translateInterfaceText(table.object_type || 'Таблица'))}</span>
            </button>`;
        }).join('');
    }

    function selectDistributionTable(table) {
        const select = document.getElementById('distributionTableSelect');
        selectedDistributionTable = table || null;
        if (select) select.value = table ? distributionTableOptionLabel(table) : '';
        closeDistributionTablePicker();
        refreshDistributionForSelectedTable();
    }

    function refreshDistributionForSelectedTable() {
        const select = document.getElementById('distributionTableSelect');
        const selectedValue = (select?.value || '').trim();
        const selectedTable = distributionTables.find(table => distributionTableOptionLabel(table) === selectedValue)
            || selectedDistributionTable;
        const requestId = ++distributionRequestId;
        if (!selectedTable) {
            renderDistributionWarning('Выберите таблицу для расчёта распределения');
            return;
        }
        const {schema_name: schemaName, table_name: tableName} = selectedTable;
        const conn = connections.find(c => String(c.id) === String(activeConnectionId));
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderDistributionWarning('Выберите сохранённое подключение для расчёта распределения');
            return;
        }
        renderDistributionWarning('Загрузка распределения строк по сегментам...');
        connectionRequest(distributionInfoApiUrl, {id: conn.id, schema_name: schemaName, table_name: tableName})
            .then(data => {
                if (requestId === distributionRequestId) renderDistributionInfo(data);
            })
            .catch(error => {
                if (requestId === distributionRequestId) renderDistributionWarning(error.message || 'Не удалось получить распределение');
            });
    }

    function renderDistributionTableOptions(tables) {
        const select = document.getElementById('distributionTableSelect');
        const count = document.getElementById('distributionTableCount');
        if (count) count.textContent = `${tables.length} таблиц`;
        if (!select) return;
        if (!tables.length) {
            selectedDistributionTable = null;
            select.value = '';
            select.placeholder = 'Таблицы не найдены';
            closeDistributionTablePicker();
            renderDistributionWarning('Таблицы не найдены');
            return;
        }
        select.placeholder = 'Начните вводить схему или название таблицы';
        const previousLabel = selectedDistributionTable ? distributionTableOptionLabel(selectedDistributionTable) : select.value;
        selectedDistributionTable = tables.find(table => distributionTableOptionLabel(table) === previousLabel) || tables[0];
        select.value = distributionTableOptionLabel(selectedDistributionTable);
        renderDistributionPickerOptions(tables);
        refreshDistributionForSelectedTable();
    }

    function refreshDistributionTablesForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const select = document.getElementById('distributionTableSelect');
        const options = document.getElementById('distributionTableOptions');
        const requestId = ++distributionTablesRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            distributionTables = [];
            selectedDistributionTable = null;
            if (select) {
                select.value = '';
                select.placeholder = 'Выберите сохранённое подключение для загрузки таблиц';
            }
            if (options) options.innerHTML = '';
            closeDistributionTablePicker();
            renderDistributionWarning('Выберите сохранённое подключение для загрузки списка таблиц');
            return;
        }
        if (select) {
            select.value = '';
            select.placeholder = 'Загрузка таблиц...';
        }
        if (options) options.innerHTML = '';
        closeDistributionTablePicker();
        connectionRequest(distributionTablesApiUrl, {id: conn.id})
            .then(data => {
                if (requestId !== distributionTablesRequestId) return;
                distributionTables = data.tables || [];
                renderDistributionTableOptions(distributionTables);
            })
            .catch(error => {
                if (requestId !== distributionTablesRequestId) return;
                distributionTables = [];
                selectedDistributionTable = null;
                if (select) {
                    select.value = '';
                    select.placeholder = 'Не удалось загрузить таблицы';
                }
                if (options) options.innerHTML = '';
                renderDistributionWarning(error.message || 'Не удалось загрузить список таблиц');
            });
    }

    function initDistributionControls() {
        const select = document.getElementById('distributionTableSelect');
        const options = document.getElementById('distributionTableOptions');
        select?.addEventListener('focus', function() {
            this.select();
            openDistributionTablePicker('');
        });
        select?.addEventListener('input', function() {
            selectedDistributionTable = null;
            openDistributionTablePicker(this.value);
        });
        select?.addEventListener('keydown', function(event) {
            const optionButtons = [...(options?.querySelectorAll('.distribution-table-option') || [])];
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                if (options?.hidden) openDistributionTablePicker(this.value);
                const visibleOptions = [...(options?.querySelectorAll('.distribution-table-option') || [])];
                if (!visibleOptions.length) return;
                distributionPickerActiveIndex = event.key === 'ArrowDown'
                    ? Math.min(distributionPickerActiveIndex + 1, visibleOptions.length - 1)
                    : Math.max(distributionPickerActiveIndex - 1, 0);
                visibleOptions.forEach((option, index) => option.classList.toggle('is-active', index === distributionPickerActiveIndex));
                visibleOptions[distributionPickerActiveIndex].scrollIntoView({block: 'nearest'});
                return;
            }
            if (event.key === 'Enter') {
                event.preventDefault();
                const activeOption = optionButtons[distributionPickerActiveIndex];
                const label = activeOption?.dataset.tableLabel || this.value.trim();
                const table = distributionTables.find(item => distributionTableOptionLabel(item) === label);
                if (table) selectDistributionTable(table);
                else refreshDistributionForSelectedTable();
            } else if (event.key === 'Escape') {
                closeDistributionTablePicker();
            }
        });
        options?.addEventListener('mousedown', event => event.preventDefault());
        options?.addEventListener('click', function(event) {
            const option = event.target.closest('.distribution-table-option');
            if (!option) return;
            const table = distributionTables.find(item => distributionTableOptionLabel(item) === option.dataset.tableLabel);
            if (table) selectDistributionTable(table);
        });
        document.getElementById('distributionTableToggle')?.addEventListener('click', function() {
            if (options?.hidden) openDistributionTablePicker('');
            else closeDistributionTablePicker();
            select?.focus();
        });
        document.getElementById('distributionRefreshBtn')?.addEventListener('click', refreshDistributionForSelectedTable);
        document.addEventListener('click', function(event) {
            if (!event.target.closest('#distributionTablePicker')) closeDistributionTablePicker();
        });
        document.querySelectorAll('[data-distribution-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const column = this.dataset.distributionSort;
                if (distributionSortState.column === column) {
                    distributionSortState.direction = distributionSortState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    distributionSortState = {column, direction: column === 'segment_id' ? 'asc' : 'desc'};
                }
                renderDistributionRows();
            });
        });
        updateDistributionSortIndicators();
    }


    function refreshToastTablesForConnection(conn) {
        toastTablesPager.refresh(conn);
    }

    function initToastTablesControls() {
        toastTablesPager.bindControls();
    }

    function updateTempTableDistributionChart(tables = []) {
        const donut = document.getElementById('tempTableDistributionDonut');
        const summary = document.getElementById('tempTableDistributionSummary');
        const legend = document.getElementById('tempTableDistributionLegend');
        if (!donut || !summary || !legend) return;

        const colors = ['#4f8cff', '#8b5cf6', '#22c55e', '#f59e0b', '#06b6d4', '#ec4899', '#f97316', '#ef4444', '#8a9bb0'];
        const normalized = tables
            .map(table => {
                const tableName = table.table_name || '—';
                const schemaName = table.schema_name || '—';
                return {
                    name: `${schemaName}.${tableName}`,
                    sizeBytes: Number(table.size_bytes) || 0,
                    tableSize: table.table_size || `${formatDatabaseSize(table.size_bytes).value} ${formatDatabaseSize(table.size_bytes).unit}`
                };
            })
            .filter(table => table.sizeBytes > 0);
        const totalBytes = normalized.reduce((sum, table) => sum + table.sizeBytes, 0);

        if (!normalized.length || totalBytes <= 0) {
            donut.style.setProperty('--schema-distribution-gradient', '#e8eaee 0 100%');
            donut.setAttribute('aria-label', 'Нет данных о распределении данных по временным таблицам');
            summary.textContent = '—';
            legend.textContent = 'Нет данных';
            return;
        }

        const topTables = normalized.slice(0, 8);
        const otherBytes = normalized.slice(8).reduce((sum, table) => sum + table.sizeBytes, 0);
        const chartItems = otherBytes > 0
            ? [...topTables, {name: 'Остальные', sizeBytes: otherBytes, tableSize: `${formatDatabaseSize(otherBytes).value} ${formatDatabaseSize(otherBytes).unit}`}]
            : topTables;
        let cursor = 0;
        const gradient = chartItems.map((table, index) => {
            const start = cursor;
            const percent = (table.sizeBytes * 100) / totalBytes;
            cursor += percent;
            return `${colors[index % colors.length]} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
        }).join(', ');
        const totalFormatted = formatDatabaseSize(totalBytes);

        donut.style.setProperty('--schema-distribution-gradient', gradient);
        donut.setAttribute('aria-label', `Распределение данных по временным таблицам, всего ${totalFormatted.value} ${totalFormatted.unit}`);
        summary.textContent = `${totalFormatted.value} ${totalFormatted.unit}`;
        legend.innerHTML = chartItems.map((table, index) => {
            const percent = ((table.sizeBytes * 100) / totalBytes).toFixed(1);
            return `
                <div class="schema-distribution-legend-item" title="${escapeHtml(table.name)}: ${escapeHtml(table.tableSize)} (${percent}%)">
                    <span class="schema-distribution-legend-dot" style="background:${colors[index % colors.length]};"></span>
                    <span class="schema-distribution-legend-name">${escapeHtml(table.name)}</span>
                    <span class="schema-distribution-legend-value">${percent}%</span>
                </div>
            `;
        }).join('');
    }
    function refreshTempTablesForConnection(conn) {
        tempTablesPager.refresh(conn);
    }

    function initTempTablesControls() {
        document.getElementById('tempTablesTableBody')?.addEventListener('click', function (event) {
            const button = event.target.closest('.temp-table-delete-btn');
            if (!button || button.disabled) return;
            const conn = connections.find(c => String(c.id) === String(activeConnectionId));
            const schemaName = button.dataset.tempTableSchema;
            const tableName = button.dataset.tempTableName;
            if (!conn || !schemaName || !tableName) return;
            if (!confirm(translateInterfaceText(`Удалить временную таблицу "${schemaName}.${tableName}"?`))) return;

            button.disabled = true;
            connectionRequest(deleteTempTableApiUrl, {id: conn.id, schema_name: schemaName, table_name: tableName})
                .then(data => {
                    showToast(`✅ ${data.message}`);
                    refreshTempTablesForConnection(conn);
                })
                .catch(error => {
                    button.disabled = false;
                    showToast(`❌ ${error.message || 'Не удалось удалить временную таблицу'}`);
                });
        });
        tempTablesPager.bindControls();
    }

    function updateAuditPaginationButtons() {
        const totalPages = Math.max(Math.ceil(auditState.totalCount / auditState.pageSize), 1);
        const page = Math.min(auditState.page, totalPages);
        const info = document.getElementById('auditPaginationInfo');
        if (info) info.textContent = `Страница ${page} из ${totalPages}`;
        updatePaginationButtons(auditState, 'auditPrevPageBtn', 'auditNextPageBtn', page);
    }

    function initPaginationPageSizeControls() {
        const configurations = [
            ['schemaPaginationInfo', 'schemas', schemaSizesState, refreshSchemaSizesForConnection],
            ['tablePaginationInfo', 'tables', tableSizesState, refreshTableSizesForConnection],
            ['viewPaginationInfo', 'views', viewsState, refreshViewsForConnection],
            ['functionPaginationInfo', 'functions', functionsState, refreshFunctionsForConnection],
            ['tempTablePaginationInfo', 'temp-tables', tempTablesState, refreshTempTablesForConnection],
            ['toastTablePaginationInfo', 'toast-tables', toastTablesState, refreshToastTablesForConnection],
            ['usersPaginationInfo', 'users', usersState, refreshUsersForConnection],
            ['groupsPaginationInfo', 'groups', groupsState, refreshGroupsForConnection],
            ['favoritesPaginationInfo', 'favorites', favoritesState, renderFavoritesPage],
            ['maintenancePageInfo', 'maintenance', maintenanceStatsState, refreshMaintenanceStatsForConnection],
            ['auditPaginationInfo', 'audit', auditState, refreshAuditEvents]
        ];
        const labelText = window.DB_STAT_LANGUAGE === 'en' ? 'Rows:' : 'Записей:';
        configurations.forEach(([infoId, storageSuffix, state, refresh]) => {
            const info = document.getElementById(infoId);
            if (!info) return;
            const storageKey = `db_stat_page_size_${storageSuffix}`;
            const storedPageSize = Number(localStorage.getItem(storageKey));
            if (paginationPageSizeOptions.includes(storedPageSize)) state.pageSize = storedPageSize;
            const label = document.createElement('label');
            label.className = 'pagination-page-size';
            label.innerHTML = `<span>${labelText}</span><span class="pagination-page-size__select filter-select-box"><select aria-label="${labelText}">${paginationPageSizeOptions.map(size => `<option value="${size}">${size}</option>`).join('')}</select></span>`;
            const select = label.querySelector('select');
            select.value = String(state.pageSize);
            select.addEventListener('change', () => {
                state.pageSize = Number(select.value);
                state.page = 1;
                localStorage.setItem(storageKey, select.value);
                refresh();
            });
            info.parentElement?.insertBefore(label, info);

            const bottomPagination = info.closest('.table-pagination');
            const table = bottomPagination?.parentElement?.querySelector('.table-responsive');
            if (!bottomPagination || !table) return;
            const topPagination = bottomPagination.cloneNode(true);
            topPagination.classList.add('table-pagination--top');
            topPagination.querySelectorAll('[id]').forEach(element => element.removeAttribute('id'));
            const bottomButtons = bottomPagination.querySelectorAll('.btn-conn');
            const topButtons = topPagination.querySelectorAll('.btn-conn');
            const topInfo = Array.from(topPagination.children).find(element => element.tagName === 'SPAN');
            const topSelect = topPagination.querySelector('.pagination-page-size select');
            const syncTopPagination = () => {
                if (topButtons[0]) topButtons[0].disabled = bottomButtons[0]?.disabled ?? true;
                if (topButtons[1]) topButtons[1].disabled = bottomButtons[1]?.disabled ?? true;
                if (topInfo) topInfo.textContent = info.textContent;
                if (topSelect) topSelect.value = select.value;
            };
            topButtons[0]?.addEventListener('click', () => bottomButtons[0]?.click());
            topButtons[1]?.addEventListener('click', () => bottomButtons[1]?.click());
            topSelect?.addEventListener('change', () => {
                select.value = topSelect.value;
                select.dispatchEvent(new Event('change'));
            });
            new MutationObserver(syncTopPagination).observe(bottomPagination, {
                attributes: true,
                childList: true,
                subtree: true,
                characterData: true
            });
            syncTopPagination();
            table.parentElement.insertBefore(topPagination, table);
        });
    }

    function renderAuditWarning(message) {
        const tbody = document.getElementById('auditEventsTableBody');
        const count = document.getElementById('auditEventsCount');
        if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-muted">${escapeHtml(message)}</td></tr>`;
        if (count) count.textContent = 'Нет данных';
        auditState.totalCount = 0;
        updateAuditPaginationButtons();
    }

    function populateAuditActionFilter(actions) {
        const select = document.getElementById('auditActionFilter');
        if (!select || auditActionsLoaded) return;
        const currentValue = select.value;
        select.innerHTML = '<option value="">Все действия</option>';
        (actions || []).forEach(action => {
            const option = document.createElement('option');
            option.value = action.value;
            option.textContent = action.label;
            option.classList.add(`audit-action-filter-option--${action.value.replaceAll('_', '-')}`);
            select.appendChild(option);
        });
        select.value = currentValue;
        updateAuditActionFilterColor(select);
        auditActionsLoaded = true;
    }

    function populateAuditUserFilter(users) {
        const select = document.getElementById('auditUserFilter');
        if (!select || auditUsersLoaded) return;
        const currentValue = select.value;
        select.innerHTML = '<option value="">Все пользователи</option>';
        (users || []).forEach(username => {
            const option = document.createElement('option');
            option.value = username;
            option.textContent = username;
            select.appendChild(option);
        });
        select.value = currentValue;
        auditUsersLoaded = true;
    }

    function updateAuditSortIndicators() {
        document.querySelectorAll('[data-audit-sort]').forEach(button => {
            const isActive = button.dataset.auditSort === auditState.sort;
            button.classList.toggle('active', isActive);
            updateSortHeaderState(button, isActive, auditState.direction);
        });
    }

    function updateAuditActionFilterColor(select) {
        if (!select) return;
        if (select.dataset.actionColorClass) {
            select.classList.remove(select.dataset.actionColorClass);
        }
        const actionColorClass = select.value ? `audit-action-filter--${select.value.replaceAll('_', '-')}` : '';
        if (actionColorClass) {
            select.classList.add(actionColorClass);
        }
        select.dataset.actionColorClass = actionColorClass;
    }

    function getAuditActionBadgeClass(actionType) {
        const classes = {
            login: 'audit-action-badge--login',
            logout: 'audit-action-badge--logout',
            connection_create: 'audit-action-badge--connection-create',
            connection_update: 'audit-action-badge--connection-update',
            connection_delete: 'audit-action-badge--connection-delete',
            connection_test: 'audit-action-badge--connection-test',
            sidebar_settings: 'audit-action-badge--sidebar-settings',
            favorite_add: 'audit-action-badge--favorite-add',
            favorite_remove: 'audit-action-badge--favorite-remove',
            query_terminate: 'audit-action-badge--query-terminate',
            session_terminate: 'audit-action-badge--session-terminate',
            lock_terminate: 'audit-action-badge--session-terminate',
            transaction_terminate: 'audit-action-badge--query-terminate',
            vacuum: 'audit-action-badge--vacuum',
            vacuum_full: 'audit-action-badge--vacuum-full',
            analyze: 'audit-action-badge--analyze',
            explain_analyze: 'audit-action-badge--explain-analyze'
        };
        return classes[actionType] || 'audit-action-badge--default';
    }

    function renderAuditEvents(data) {
        populateAuditActionFilter(data.actions || []);
        populateAuditUserFilter(data.users || []);
        const events = data.events || [];
        auditState.page = data.page || auditState.page;
        auditState.pageSize = data.page_size || auditState.pageSize;
        auditState.totalCount = data.total_count || 0;
        auditState.sort = data.sort || auditState.sort;
        auditState.direction = data.direction || auditState.direction;
        const tbody = document.getElementById('auditEventsTableBody');
        const count = document.getElementById('auditEventsCount');
        if (count) {
            count.textContent = `${events.length} из ${auditState.totalCount} записей`;
        }
        updateAuditPaginationButtons();
        updateAuditSortIndicators();
        if (!tbody) return;
        if (!events.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-muted">События аудита не найдены</td></tr>';
            return;
        }
        tbody.innerHTML = events.map(event => `
            <tr>
                <td class="audit-created">${escapeHtml(event.created)}</td>
                <td><strong>${escapeHtml(event.username)}</strong></td>
                <td><span class="audit-action-badge ${getAuditActionBadgeClass(event.action_type)}">${escapeHtml(event.action_label || event.action_type)}</span></td>
                <td class="audit-info-cell">${escapeHtml(event.info)}</td>
            </tr>
        `).join('');
    }

    function refreshAuditEvents() {
        const requestId = ++auditRequestId;
        const actionType = document.getElementById('auditActionFilter')?.value || '';
        const username = document.getElementById('auditUserFilter')?.value || '';
        const createdFrom = document.getElementById('auditDateFrom')?.value || '';
        const createdTo = document.getElementById('auditDateTo')?.value || '';
        const params = new URLSearchParams({page: String(auditState.page), page_size: String(auditState.pageSize), sort: auditState.sort, direction: auditState.direction});
        if (actionType) params.set('action_type', actionType);
        if (username) params.set('username', username);
        if (createdFrom) params.set('created_from', createdFrom);
        if (createdTo) params.set('created_to', createdTo);
        const url = `${auditEventsApiUrl}?${params.toString()}`;
        renderAuditWarning('Загрузка аудита...');
        fetch(url)
            .then(async response => {
                const data = await response.json().catch(() => ({}));
                if (!response.ok || data.ok === false) {
                    throw new Error(data.message || 'Не удалось получить аудит');
                }
                return data;
            })
            .then(data => {
                if (requestId === auditRequestId) renderAuditEvents(data);
            })
            .catch(error => {
                if (requestId === auditRequestId) renderAuditWarning(error.message || 'Не удалось получить аудит');
            });
    }

    function initAuditControls() {
        document.getElementById('auditActionFilter')?.addEventListener('change', function () {
            updateAuditActionFilterColor(this);
            auditState.page = 1;
            refreshAuditEvents();
        });
        document.getElementById('auditUserFilter')?.addEventListener('change', function () {
            auditState.page = 1;
            refreshAuditEvents();
        });
        ['auditDateFrom', 'auditDateTo'].forEach(inputId => {
            const input = document.getElementById(inputId);
            const updateDatePlaceholder = () => input?.parentElement?.classList.toggle('has-value', Boolean(input.value));
            // Clicking a datetime-local input only focuses a segment for typing —
            // the browser opens the native picker only via its own calendar icon.
            // Opening it for a click anywhere in the field (not just the icon)
            // requires calling showPicker() explicitly.
            input?.parentElement?.addEventListener('click', () => {
                if (typeof input.showPicker === 'function') {
                    try {
                        input.showPicker();
                    } catch (error) {
                        // Ignored: some browsers refuse showPicker() outside a
                        // direct user gesture or when the input is disabled.
                    }
                }
            });
            input?.addEventListener('input', updateDatePlaceholder);
            input?.addEventListener('change', function () {
                updateDatePlaceholder();
                const dateFrom = document.getElementById('auditDateFrom');
                const dateTo = document.getElementById('auditDateTo');
                if (dateFrom && dateTo) {
                    dateFrom.max = dateTo.value;
                    dateTo.min = dateFrom.value;
                }
                auditState.page = 1;
                refreshAuditEvents();
            });
            updateDatePlaceholder();
        });
        document.querySelectorAll('[data-audit-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.auditSort;
                auditState.direction = auditState.sort === sort && auditState.direction === 'asc' ? 'desc' : 'asc';
                auditState.sort = sort;
                auditState.page = 1;
                refreshAuditEvents();
            });
        });
        document.getElementById('auditRefreshBtn')?.addEventListener('click', refreshAuditEvents);
        document.getElementById('auditPrevPageBtn')?.addEventListener('click', function () {
            if (auditState.page > 1) {
                auditState.page -= 1;
                refreshAuditEvents();
            }
        });
        document.getElementById('auditNextPageBtn')?.addEventListener('click', function () {
            const totalPages = Math.max(Math.ceil(auditState.totalCount / auditState.pageSize), 1);
            if (auditState.page < totalPages) {
                auditState.page += 1;
                refreshAuditEvents();
            }
        });
        updateAuditPaginationButtons();
        updateAuditSortIndicators();
    }

    function connectionRequest(url, payload) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), CONNECTION_REQUEST_TIMEOUT_MS);
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        }).then(async response => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.ok === false) {
                throw new Error(data.message || 'Ошибка запроса');
            }
            return data;
        }).catch(error => {
            if (error.name === 'AbortError') {
                throw new Error('База данных не ответила за 20 секунд. Возможно, объект заблокирован или сервер перегружен');
            }
            throw error;
        }).finally(() => clearTimeout(timer));
    }

    function initDatabasePdfReport() {
        const button = document.getElementById('databasePdfReportBtn');
        if (!button) return;
        button.addEventListener('click', async function () {
            const conn = connections.find(item => String(item.id) === String(activeConnectionId));
            if (!conn) {
                showToast('⚠️ Выберите подключение для формирования отчёта');
                return;
            }
            button.disabled = true;
            try {
                const response = await fetch(databasePdfReportApiUrl, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
                    body: JSON.stringify({id: conn.id})
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok || data.ok === false) {
                    throw new Error(data.message || 'Не удалось сформировать PDF-отчёт');
                }
                showToast('✅ Формирование PDF запущено в фоне');
                document.dispatchEvent(new CustomEvent('dbstat:reports-changed'));
                loadBackgroundJobs();
                pollReportJob(data.job.id);
            } catch (error) {
                showToast(`❌ ${error.message || 'Не удалось сформировать PDF-отчёт'}`);
            } finally {
                button.disabled = !activeConnectionId;
            }
        });
    }

    function pollReportJob(jobId) {
        window.setTimeout(async () => {
            try {
                const response = await fetch(`${databasePdfReportApiUrl}?job_id=${encodeURIComponent(jobId)}`);
                const data = await response.json().catch(() => ({}));
                if (!response.ok || data.ok === false) throw new Error(data.message || 'Не удалось проверить состояние PDF-отчёта');
                document.dispatchEvent(new CustomEvent('dbstat:reports-changed'));
                loadBackgroundJobs();
                if (['queued', 'running'].includes(data.job.status)) {
                    pollReportJob(jobId);
                } else if (data.job.status === 'completed') {
                    showToast('✅ PDF-отчёт готов. Скачать его можно в «Фоновых операциях»');
                } else {
                    showToast(`❌ ${data.job.message || 'Не удалось сформировать PDF-отчёт'}`);
                }
            } catch (error) {
                showToast(`❌ ${error.message}`);
            }
        }, 2000);
    }



    function getStoredActiveConnectionId() {
        return localStorage.getItem(activeConnectionStorageKey);
    }

    function persistActiveConnectionId(connId) {
        if (connId) {
            localStorage.setItem(activeConnectionStorageKey, String(connId));
        } else {
            localStorage.removeItem(activeConnectionStorageKey);
        }
    }

    function getInitialActiveConnectionId() {
        const storedConnectionId = getStoredActiveConnectionId();
        const storedConnection = connections.find(conn => String(conn.id) === String(storedConnectionId));
        return storedConnection?.id || connections[0]?.id || null;
    }

    function loadConnections() {
        fetch(connectionApiUrl)
            .then(response => response.json())
            .then(data => {
                connections = data.connections || [];
                activeConnectionId = getInitialActiveConnectionId();
                persistActiveConnectionId(activeConnectionId);
                populateConnectionSelect();
                activatePage(getStoredActivePage() || getCurrentActivePageId(), {persist: false, refresh: false});
                refreshActivePageForConnection();
            })
            .catch(() => {
                connections = [];
                activeConnectionId = null;
                persistActiveConnectionId(null);
                populateConnectionSelect();
                refreshActivePageForConnection();
                showToast('⚠️ Не удалось загрузить список доступных подключений');
            });
    }

    function roleLabel(role) {
        return role === 'p' ? 'primary' : role === 'm' ? 'mirror' : role;
    }

    function statusBadge(status) {
        return status === 'u' ? '<span class="status-badge up">up</span>' : '<span class="status-badge down">down</span>';
    }

    function modeBadge(mode) {
        return mode === 's' ? '<span class="status-badge sync">sync</span>' : '<span class="status-badge unsync">not sync</span>';
    }

    function segmentSortValue(segment, column) {
        if (column === 'segment') {
            const numericSegment = Number(segment.segment);
            return Number.isNaN(numericSegment) ? String(segment.segment || '') : numericSegment;
        }
        if (column === 'role') return roleLabel(segment.role || '');
        if (column === 'status') return segment.status === 'u' ? 'up' : 'down';
        if (column === 'mode') return segment.mode === 's' ? 'sync' : 'not sync';
        if (column === 'host') return segment.hostname || segment.address || '';
        return '';
    }

    function sortSegments(segments) {
        const {column, direction} = segmentsSortState;
        const multiplier = direction === 'asc' ? 1 : -1;
        return [...segments].sort((left, right) => {
            const leftValue = segmentSortValue(left, column);
            const rightValue = segmentSortValue(right, column);

            if (typeof leftValue === 'number' && typeof rightValue === 'number') {
                return (leftValue - rightValue) * multiplier;
            }

            return String(leftValue).localeCompare(String(rightValue), 'ru', {numeric: true, sensitivity: 'base'}) * multiplier;
        });
    }

    function updateSegmentsSortIndicators() {
        document.querySelectorAll('[data-segments-sort]').forEach(button => {
            const isActive = button.dataset.segmentsSort === segmentsSortState.column;
            button.classList.toggle('active', isActive);
            updateSortHeaderState(button, isActive, segmentsSortState.direction);
        });
    }

    function initSegmentsTableSorting() {
        document.querySelectorAll('[data-segments-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const column = this.dataset.segmentsSort;
                if (segmentsSortState.column === column) {
                    segmentsSortState.direction = segmentsSortState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    segmentsSortState = {column, direction: 'asc'};
                }
                if (currentSegmentsWarningHtml) {
                    updateSegmentsSortIndicators();
                    return;
                }
                renderSegmentsTable(currentSegments);
            });
        });
        updateSegmentsSortIndicators();
    }

    function renderSegmentMetrics(metrics) {
        const container = document.getElementById('segmentMetricsSummary');
        if (!container) return;
        container.innerHTML = metrics.map(metric => `
            <div class="segment-metric">
                <div class="metric-value">${Number(metric.value).toFixed(metric.name.includes('Процент') ? 0 : 0)}</div>
                <div class="metric-name">${escapeHtml(metric.name)}</div>
            </div>
        `).join('');
    }

    function renderSegmentsTable(segments) {
        const tbody = document.getElementById('segmentsTableBody');
        if (!tbody) return;
        updateSegmentsSortIndicators();
        if (currentSegmentsWarningHtml && !segments.length) {
            tbody.innerHTML = `<tr><td colspan="5">${currentSegmentsWarningHtml}</td></tr>`;
            return;
        }
        currentSegmentsWarningHtml = '';
        tbody.innerHTML = sortSegments(segments).map(segment => `
            <tr>
                <td><strong>${escapeHtml(segment.segment)}</strong></td>
                <td>${escapeHtml(roleLabel(segment.role))}</td>
                <td>${statusBadge(segment.status)}</td>
                <td>${modeBadge(segment.mode)}</td>
                <td>${escapeHtml(segment.hostname || segment.address || '-')}</td>
            </tr>
        `).join('');
    }

    function updateSegmentsChart(segments) {
        if (!charts.segments) return;
        const contents = [...new Set(segments.filter(segment => Number(segment.segment) >= 0).map(segment => String(segment.segment)))].sort((a, b) => Number(a) - Number(b));
        charts.segments.data.labels = contents.map(content => translateInterfaceText(`Сегмент ${content}`));
        charts.segments.data.datasets[0].data = contents.map(content => segments.filter(segment => String(segment.segment) === content && segment.role === 'p').length);
        charts.segments.data.datasets[1].data = contents.map(content => segments.filter(segment => String(segment.segment) === content && segment.role === 'm').length);
        charts.segments.update();
    }

    function formatSegmentError(message) {
        const normalized = String(message || '').replace(/\s+/g, ' ').trim();
        if (normalized.includes('gp_segment_configuration') || normalized.includes('не существует')) {
            return {
                title: 'Сегменты недоступны для выбранного подключения',
                text: 'Выбранное подключение не похоже на Greenplum/Greengage или у пользователя нет доступа к gp_segment_configuration. Выберите подключение Greenplum/Greengage или проверьте права доступа.'
            };
        }
        return {
            title: 'Не удалось обновить информацию о сегментах',
            text: normalized || 'Проверьте доступность подключения и повторите попытку.'
        };
    }

    function setSegmentsChartEmpty(isVisible, text = 'Информация о сегментах недоступна') {
        const empty = document.getElementById('segmentsChartEmpty');
        if (!empty) return;
        empty.classList.toggle('d-none', !isVisible);
        const label = empty.querySelector('span');
        if (label) label.textContent = text;
    }

    function renderSegmentsWarning(message) {
        const warning = formatSegmentError(message);
        const badge = document.getElementById('segmentHealthBadge');
        if (badge) {
            badge.className = 'badge badge-soft-warning';
            badge.textContent = 'Недоступно';
        }

        const warningHtml = `
            <div class="segment-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <div>
                    <strong>${escapeHtml(warning.title)}</strong>
                    <span>${escapeHtml(warning.text)}</span>
                </div>
            </div>
        `;

        const metrics = document.getElementById('segmentMetricsSummary');
        if (metrics) metrics.innerHTML = warningHtml;
        currentSegments = [];
        currentSegmentsWarningHtml = warningHtml;
        updateSegmentsSortIndicators();

        const tbody = document.getElementById('segmentsTableBody');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="5">${warningHtml}</td></tr>`;
        }

        if (charts.segments) {
            charts.segments.data.labels = [];
            charts.segments.data.datasets[0].data = [];
            charts.segments.data.datasets[1].data = [];
            charts.segments.update();
        }
        setSegmentsChartEmpty(true, warning.title);
    }

    function renderSegmentsInfo(data) {
        const badge = document.getElementById('segmentHealthBadge');
        if (badge) {
            const hasProblem = data.health && !data.health.includes('Все сегменты');
            badge.className = `badge ${hasProblem ? 'badge-soft-danger' : 'badge-soft-success'}`;
            badge.textContent = data.health || 'Нет данных';
        }
        setSegmentsChartEmpty(false);
        currentSegmentsWarningHtml = '';
        currentSegments = data.segments || [];
        renderSegmentMetrics(data.metrics || []);
        renderSegmentsTable(currentSegments);
        updateSegmentsChart(currentSegments);
    }

    function refreshSegmentsForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderSegmentsWarning('Информация о сегментах недоступна: выберите сохранённое подключение Greenplum или Greengage.');
            return;
        }

        const badge = document.getElementById('segmentHealthBadge');
        if (badge) {
            badge.className = 'badge badge-soft-info';
            badge.textContent = 'Обновление...';
        }

        const requestId = ++segmentsRequestId;
        connectionRequest(segmentsInfoApiUrl, {id: conn.id})
            .then(data => {
                if (requestId === segmentsRequestId) renderSegmentsInfo(data);
            })
            .catch(error => {
                if (requestId === segmentsRequestId) renderSegmentsWarning(error.message || 'Информация о сегментах недоступна для выбранного подключения.');
            });
    }


    function updateConnectionTooltip(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const database = document.getElementById('connectionTooltipDatabase');
        const host = document.getElementById('connectionTooltipHost');
        const port = document.getElementById('connectionTooltipPort');
        const owner = document.getElementById('connectionTooltipOwner');
        const select = document.getElementById('connectionSelect');
        const icon = document.getElementById('connectionSelectIcon');
        const label = document.getElementById('connectionSelectLabel');
        const databaseValue = conn?.database || '—';
        const hostValue = conn?.host || '—';
        const portValue = conn?.port || '—';
        const ownerValue = conn?.created_by || '—';

        if (database) database.textContent = databaseValue;
        if (host) host.textContent = hostValue;
        if (port) port.textContent = portValue;
        if (owner) owner.textContent = ownerValue;
        if (label) label.textContent = conn?.name || select?.selectedOptions?.[0]?.textContent || 'Нет доступных подключений';
        if (icon) {
            const iconSrc = getConnectionDbTypeIconSrc(conn?.db_type, icon);
            if (conn && iconSrc) icon.src = iconSrc;
            icon.classList.toggle('d-none', !conn);
        }
        document.querySelectorAll('.connection-select__option').forEach(option => {
            const isSelected = conn && String(option.dataset.value) === String(conn.id);
            option.classList.toggle('is-selected', Boolean(isSelected));
            option.setAttribute('aria-selected', String(Boolean(isSelected)));
        });
    }

    function initConnectionSelect() {
        const wrapper = document.querySelector('.connection-select');
        const manager = wrapper?.closest('.connection-manager');
        const toggle = document.getElementById('connectionSelectToggle');
        const select = document.getElementById('connectionSelect');
        const menu = document.getElementById('connectionSelectMenu');
        if (!wrapper || !manager || !toggle || !select || !menu) return;

        const closeMenu = () => {
            wrapper.classList.remove('open');
            toggle.setAttribute('aria-expanded', 'false');
        };

        toggle.addEventListener('click', () => {
            const shouldOpen = !wrapper.classList.contains('open');
            manager.classList.remove('connection-manager--info-open');
            document.getElementById('connectionInfoToggle')?.setAttribute('aria-expanded', 'false');
            wrapper.classList.toggle('open', shouldOpen);
            toggle.setAttribute('aria-expanded', String(shouldOpen));
        });

        menu.addEventListener('click', event => {
            const option = event.target.closest('.connection-select__option');
            if (!option || option.disabled) return;
            select.value = option.dataset.value;
            select.dispatchEvent(new Event('change', {bubbles: true}));
            closeMenu();
            toggle.focus();
        });

        document.addEventListener('click', event => {
            if (!wrapper.contains(event.target)) closeMenu();
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') closeMenu();
        });
    }

    function initConnectionInfoTooltip() {
        const manager = document.querySelector('.connection-manager');
        const toggle = document.getElementById('connectionInfoToggle');
        if (!manager || !toggle) return;

        const closeTooltip = () => {
            manager.classList.remove('connection-manager--info-open');
            toggle.setAttribute('aria-expanded', 'false');
        };

        toggle.addEventListener('click', event => {
            event.stopPropagation();
            const shouldOpen = !manager.classList.contains('connection-manager--info-open');
            manager.classList.toggle('connection-manager--info-open', shouldOpen);
            toggle.setAttribute('aria-expanded', String(shouldOpen));
        });
        document.addEventListener('click', event => {
            if (!manager.contains(event.target)) closeTooltip();
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') closeTooltip();
        });
    }

    function populateConnectionSelect() {
        const select = document.getElementById('connectionSelect');
        const menu = document.getElementById('connectionSelectMenu');
        select.innerHTML = '';
        menu.innerHTML = '';
        if (!connections.length) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Нет доступных подключений';
            select.appendChild(option);
            const menuOption = document.createElement('button');
            menuOption.className = 'connection-select__option';
            menuOption.type = 'button';
            menuOption.disabled = true;
            menuOption.textContent = option.textContent;
            menu.appendChild(menuOption);
            select.value = '';
            updateConnectionTooltip(null);
            updateConnectionActionButtons(null);
            updateSidebarForConnection(null);
            persistActiveConnectionId(null);
            return;
        }
        connections.forEach(conn => {
            const option = document.createElement('option');
            option.value = conn.id;
            option.textContent = conn.name;
            select.appendChild(option);

            const menuOption = document.createElement('button');
            menuOption.className = 'connection-select__option';
            menuOption.type = 'button';
            menuOption.setAttribute('role', 'option');
            menuOption.dataset.value = conn.id;
            const menuOptionIconSrc = getConnectionDbTypeIconSrc(conn.db_type, document.getElementById('connectionSelectIcon'));
            if (menuOptionIconSrc) {
                const menuOptionIcon = document.createElement('img');
                menuOptionIcon.className = 'connection-select__option-icon';
                menuOptionIcon.src = menuOptionIconSrc;
                menuOptionIcon.alt = '';
                menuOption.appendChild(menuOptionIcon);
            }
            const menuOptionLabel = document.createElement('span');
            menuOptionLabel.textContent = conn.name;
            menuOption.appendChild(menuOptionLabel);
            menu.appendChild(menuOption);
        });
        if (activeConnectionId) {
            select.value = activeConnectionId;
            persistActiveConnectionId(activeConnectionId);
        }
        updateConnectionTooltip();
        updateConnectionActionButtons();
        updateSidebarForConnection();
    }

    function isKnownPage(pageId) {
        if (!pageId || !pageTitles[pageId] || !document.getElementById('page-' + pageId)) return false;
        if (pageId === 'home') return true;
        return Boolean(
            isPageAvailableForConnection(pageId) &&
            Array.from(document.querySelectorAll('.nav-item[data-page]')).some(item => item.dataset.page === pageId && !item.classList.contains('d-none'))
        );
    }

    function getStoredActivePage() {
        const pageId = localStorage.getItem(activePageStorageKey);
        return isKnownPage(pageId) ? pageId : null;
    }

    function getCurrentActivePageId() {
        const activeNavItem = document.querySelector('.nav-item.active');
        if (isKnownPage(activeNavItem?.dataset.page)) return activeNavItem.dataset.page;

        const activePage = document.querySelector('.page.active');
        if (activePage?.id?.startsWith('page-')) {
            const pageId = activePage.id.replace('page-', '');
            if (isKnownPage(pageId)) return pageId;
        }

        return 'database-overview';
    }

    function refreshPageData(pageId, conn) {
        if (pageId === 'segments') {
            refreshSegmentsForConnection(conn);
        }
        if (pageId === 'database-overview') {
            refreshDatabaseOverviewForConnection(conn);
        }
        if (pageId === 'databases') {
            refreshSchemaSizesForConnection(conn);
        }
        if (pageId === 'tables') {
            refreshTableSizesForConnection(conn);
        }
        if (pageId === 'views') {
            refreshViewsForConnection(conn);
        }
        if (pageId === 'functions') {
            refreshFunctionsForConnection(conn);
        }
        if (pageId === 'toast-tables') {
            refreshToastTablesForConnection(conn);
        }
        if (pageId === 'temp-tables') {
            refreshTempTablesForConnection(conn);
        }
        if (pageId === 'distribution') {
            refreshDistributionTablesForConnection(conn);
        }
        if (pageId === 'queries') {
            refreshActiveQueriesForConnection(conn);
        }
        if (pageId === 'sessions') {
            refreshActiveSessionsForConnection(conn);
        }
        if (pageId === 'locks') {
            refreshBlockingLocksForConnection(conn);
        }
        if (pageId === 'transactions') {
            refreshIdleTransactionsForConnection(conn);
        }
        if (pageId === 'memory') {
            refreshMemoryOverviewForConnection(conn);
        }
        if (pageId === 'users') {
            refreshUsersForConnection(conn);
        }
        if (pageId === 'groups') {
            refreshGroupsForConnection(conn);
        }
        if (pageId === 'maintenance') {
            maintenanceStatsState.page = 1;
            refreshMaintenanceStatsForConnection(conn);
        }
        if (pageId === 'audit') {
            refreshAuditEvents();
        }
        if (pageId === 'favorites') {
            loadFavorites(conn?.id || activeConnectionId).catch(error => {
                renderFavoritesPage();
                showToast(`❌ ${error.message || 'Не удалось загрузить избранное'}`);
            });
        }
    }

    function refreshActivePageForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        // Background prefetch (runs regardless of which page is active) — logged
        // rather than surfaced to the user, who may be looking at a different
        // page entirely; the Favorites page itself reports errors when visited.
        if (conn?.id) loadFavorites(conn.id).catch(error => console.warn('Не удалось предзагрузить избранное:', error));
        refreshPageData(getCurrentActivePageId(), conn);
    }

    function activatePage(pageId, {persist = true, refresh = true} = {}) {
        updateSidebarForConnection();
        const nextPageId = isKnownPage(pageId) ? pageId : getDefaultPageForConnection();

        document.querySelectorAll('.nav-item[data-page]').forEach(item => {
            item.classList.toggle('active', item.dataset.page === nextPageId);
        });
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        document.getElementById('page-' + nextPageId).classList.add('active');
        document.getElementById('pageTitle').innerHTML = pageTitles[nextPageId] || nextPageId;

        if (persist) {
            localStorage.setItem(activePageStorageKey, nextPageId);
        }

        if (refresh) {
            refreshPageData(nextPageId);
        }

        setTimeout(() => {
            Object.values(charts).forEach(chart => {
                if (chart && chart.resize) chart.resize();
            });
        }, 100);

        if (window.innerWidth <= 992) {
            document.getElementById('sidebar').classList.remove('open');
        }
    }

    function onConnectionChange(connId) {
        activeConnectionId = connId;
        persistActiveConnectionId(activeConnectionId);
        const conn = connections.find(c => String(c.id) === String(connId));
        updateConnectionTooltip(conn);
        updateConnectionActionButtons(conn);
        if (conn) {
            updateSidebarForConnection(conn);
            activatePage(getDefaultPageForConnection(conn));
            if (isGreenplumCompatibleConnection(conn)) {
                refreshSegmentsForConnection(conn);
            }
            showToast(`🔌 Подключено к ${conn.name}`);
            refreshAll();
        }
    }

    function openConnectionModal() {
        if (!canManageConnections()) {
            showToast('⛔ Создавать подключения может только Администратор');
            return;
        }
        connectionModalMode = 'create';
        document.getElementById('connectionModalTitle').innerHTML = '<i class="fas fa-plug me-2" style="color: var(--accent-blue);"></i>Новое подключение';
        document.getElementById('connectionSaveText').textContent = 'Подключиться';
        document.getElementById('connectionDeleteBtn').classList.add('d-none');
        document.getElementById('connId').value = '';
        modalInstance.show();
        document.getElementById('connName').value = translateInterfaceText('Новое подключение');
        document.getElementById('connHost').value = 'localhost';
        document.getElementById('connPort').value = '5432';
        document.getElementById('connDatabase').value = 'postgres';
        document.getElementById('connUser').value = 'postgres';
        setConnectionDbType('PostgreSQL');
        document.getElementById('connPassword').value = '';
    }

    function editConnection() {
        const conn = connections.find(c => String(c.id) === String(activeConnectionId));
        if (!conn) {
            showToast('⚠️ Подключение не выбрано');
            return;
        }
        if (!canEditConnection(conn)) {
            showToast('⛔ Редактировать подключение может только его создатель');
            updateConnectionActionButtons(conn);
            return;
        }

        connectionModalMode = 'edit';
        document.getElementById('connectionModalTitle').innerHTML = '<i class="fas fa-pen me-2" style="color: var(--accent-blue);"></i>Редактировать подключение';
        document.getElementById('connectionSaveText').textContent = 'Сохранить';
        document.getElementById('connectionDeleteBtn').classList.toggle('d-none', !canDeleteConnection(conn));
        document.getElementById('connId').value = /^\d+$/.test(String(conn.id)) ? conn.id : '';
        document.getElementById('connName').value = conn.name || '';
        document.getElementById('connHost').value = conn.host || 'localhost';
        document.getElementById('connPort').value = conn.port || '5432';
        document.getElementById('connDatabase').value = conn.database || 'postgres';
        document.getElementById('connUser').value = conn.user || 'postgres';
        setConnectionDbType(conn.db_type || 'PostgreSQL');
        document.getElementById('connPassword').value = '';
        modalInstance.show();
    }

    function deleteConnection() {
        if (!canManageConnections()) {
            showToast('⛔ Удалять подключения может только Администратор');
            return;
        }
        const payload = getConnectionFormData();
        const conn = connections.find(c => String(c.id) === String(activeConnectionId));
        if (!conn) {
            showToast('⚠️ Подключение не выбрано');
            return;
        }
        if (!canDeleteConnection(conn)) {
            showToast('⛔ Удалить подключение может только его создатель');
            return;
        }

        if (!confirm(translateInterfaceText(`Удалить подключение "${conn.name}"?`))) {
            return;
        }

        const finishDelete = message => {
            connections = connections.filter(item => String(item.id) !== String(activeConnectionId));
            activeConnectionId = connections[0]?.id || null;
            persistActiveConnectionId(activeConnectionId);
            populateConnectionSelect();
            refreshSegmentsForConnection();
            modalInstance.hide();
            showToast(message);
        };

        if (!payload.id) {
            finishDelete(`✅ Подключение "${conn.name}" удалено из локального списка`);
            return;
        }

        connectionRequest(connectionDeleteApiUrl, {id: payload.id})
            .then(data => finishDelete(`✅ ${data.message}`))
            .catch(error => showToast(`❌ ${error.message}`));
    }

    function saveConnection() {
        if (!canManageConnections()) {
            showToast('⛔ Сохранять подключения может только Администратор');
            return;
        }
        const payload = getConnectionFormData();

        if (!validateConnectionPayload(payload)) {
            showToast('⚠️ Заполните все обязательные поля');
            return;
        }

        showToast(`🔍 Проверка подключения "${payload.name}"...`);
        connectionRequest(connectionTestApiUrl, payload)
            .then(() => connectionRequest(connectionApiUrl, payload))
            .then(data => {
                const savedConnection = {...data.connection, status: 'online'};
                const existingIndex = connections.findIndex(conn => String(conn.id) === String(savedConnection.id) || (connectionModalMode === 'edit' && String(conn.id) === String(activeConnectionId)));
                if (existingIndex >= 0) {
                    connections[existingIndex] = savedConnection;
                } else {
                    connections.push(savedConnection);
                }
                activeConnectionId = savedConnection.id;
                persistActiveConnectionId(activeConnectionId);
                populateConnectionSelect();
                updateConnectionTooltip(savedConnection);
                updateSidebarForConnection(savedConnection);
                activatePage(getDefaultPageForConnection(savedConnection));
                if (isGreenplumCompatibleConnection(savedConnection)) {
                    refreshSegmentsForConnection(savedConnection);
                }
                modalInstance.hide();
                showToast(`✅ Подключение "${savedConnection.name}" проверено и сохранено`);
                refreshAll();
            })
            .catch(error => showToast(`❌ ${error.message}`));
    }

    function testNewConnection() {
        if (!canManageConnections()) {
            showToast('⛔ Проверять новое подключение может только Администратор');
            return;
        }
        const payload = getConnectionFormData();
        if (!validateConnectionPayload(payload)) {
            showToast('⚠️ Заполните все обязательные поля для проверки');
            return;
        }

        showToast(`🔍 Проверка ${payload.name}...`);
        connectionRequest(connectionTestApiUrl, payload)
            .then(data => showToast(`✅ ${data.message}`))
            .catch(error => showToast(`❌ ${error.message}`));
    }

    function testConnection() {
        const conn = connections.find(c => String(c.id) === String(activeConnectionId));
        if (!conn) {
            showToast('⚠️ Подключение не выбрано');
            return;
        }

        conn.status = 'connecting';
        populateConnectionSelect();
        document.getElementById('connectionSelect').value = activeConnectionId;
        showToast(`🔍 Проверка ${conn.name}...`);

        connectionRequest(connectionTestApiUrl, /^\d+$/.test(String(conn.id)) ? {id: conn.id} : conn)
            .then(data => {
                conn.status = 'online';
                    populateConnectionSelect();
                document.getElementById('connectionSelect').value = activeConnectionId;
                showToast(`✅ ${data.message}`);
            })
            .catch(error => {
                conn.status = 'offline';
                    populateConnectionSelect();
                document.getElementById('connectionSelect').value = activeConnectionId;
                showToast(`❌ ${error.message}`);
            });
    }

    function initConnectionActionButtons() {
        document.getElementById('openConnectionModalBtn')?.addEventListener('click', openConnectionModal);
        document.getElementById('testConnectionBtn')?.addEventListener('click', testConnection);
        document.getElementById('connectionEditBtn')?.addEventListener('click', editConnection);
        document.getElementById('connectionDeleteBtn')?.addEventListener('click', deleteConnection);
        document.getElementById('testNewConnectionBtn')?.addEventListener('click', testNewConnection);
        document.getElementById('saveConnectionBtn')?.addEventListener('click', saveConnection);
    }

    // ============================
    // NAVIGATION
    // ============================
    function initNavigation() {
        document.querySelectorAll('.nav-item[data-page]').forEach(item => {
            item.addEventListener('click', function (e) {
                e.preventDefault();
                activatePage(this.dataset.page);
            });
        });
    }

    // ============================
    // TOAST
    // ============================
    function showToast(message) {
        document.getElementById('toastMessage').textContent = translateInterfaceText(message);
        const toast = new bootstrap.Toast(document.getElementById('liveToast'));
        toast.show();
    }

    // ============================
    // REFRESH
    // ============================
    function refreshAll() {
        if (document.getElementById('page-segments')?.classList.contains('active')) {
            refreshSegmentsForConnection();
        }
        if (document.getElementById('page-database-overview')?.classList.contains('active')) {
            refreshDatabaseOverviewForConnection();
        }
        if (document.getElementById('page-databases')?.classList.contains('active')) {
            refreshSchemaSizesForConnection();
        }
        if (document.getElementById('page-tables')?.classList.contains('active')) {
            refreshTableSizesForConnection();
        }
        if (document.getElementById('page-views')?.classList.contains('active')) {
            refreshViewsForConnection();
        }
        if (document.getElementById('page-functions')?.classList.contains('active')) {
            refreshFunctionsForConnection();
        }
        if (document.getElementById('page-toast-tables')?.classList.contains('active')) {
            refreshToastTablesForConnection();
        }
        if (document.getElementById('page-temp-tables')?.classList.contains('active')) {
            refreshTempTablesForConnection();
        }
        if (document.getElementById('page-distribution')?.classList.contains('active')) {
            refreshDistributionTablesForConnection();
        }
        if (document.getElementById('page-queries')?.classList.contains('active')) {
            refreshActiveQueriesForConnection();
        }
        if (document.getElementById('page-locks')?.classList.contains('active')) {
            refreshBlockingLocksForConnection();
        }
        if (document.getElementById('page-transactions')?.classList.contains('active')) {
            refreshIdleTransactionsForConnection();
        }
        if (document.getElementById('page-memory')?.classList.contains('active')) {
            refreshMemoryOverviewForConnection();
        }
        if (document.getElementById('page-users')?.classList.contains('active')) {
            refreshUsersForConnection();
        }
        if (document.getElementById('page-groups')?.classList.contains('active')) {
            refreshGroupsForConnection();
        }
        if (document.getElementById('page-maintenance')?.classList.contains('active')) {
            refreshMaintenanceStatsForConnection();
        }
        Object.values(charts).forEach(chart => {
            if (chart && chart.update) chart.update();
        });
    }

    // ============================
    // CHARTS - Light Theme
    // ============================
    function initCharts() {
        const colors = {
            blue: '#4f8cff',
            green: '#22c55e',
            yellow: '#f59e0b',
            red: '#ef4444',
            purple: '#8b5cf6',
            teal: '#06b6d4',
            orange: '#f97316',
            pink: '#ec4899',
            gray: 'rgba(0,0,0,0.08)'
        };

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#4a5568',
                        boxWidth: 12,
                        padding: 12,
                        font: {size: 11, family: 'Inter'}
                    }
                }
            },
            scales: {
                x: {
                    ticks: {color: '#8a9bb0', font: {size: 9, family: 'Inter'}},
                    grid: {color: 'rgba(0,0,0,0.04)'}
                },
                y: {
                    ticks: {color: '#8a9bb0', font: {size: 9, family: 'Inter'}},
                    grid: {color: 'rgba(0,0,0,0.04)'}
                }
            }
        };

        // ---- 3. Segments ----
        const ctx3 = document.getElementById('segmentsChart').getContext('2d');
        charts.segments = new Chart(ctx3, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {label: 'Primary', data: [], backgroundColor: colors.blue},
                    {label: 'Mirror', data: [], backgroundColor: colors.teal}
                ]
            },
            options: {
                ...chartOptions,
                scales: {
                    x: {stacked: true, ticks: {color: '#8a9bb0', font: {size: 10, family: 'Inter'}}, grid: {color: 'rgba(0,0,0,0.04)'}},
                    y: {stacked: true, ticks: {stepSize: 1, color: '#8a9bb0', font: {size: 9, family: 'Inter'}}, grid: {color: 'rgba(0,0,0,0.04)'}}
                },
                plugins: {
                    legend: {labels: {color: '#4a5568', boxWidth: 12, font: {size: 11, family: 'Inter'}}}
                }
            }
        });

        // ---- 8. Segment Distribution ----
        const ctx8 = document.getElementById('segmentDistributionChart').getContext('2d');
        charts.segmentDist = new Chart(ctx8, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: translateInterfaceText('Строк'),
                    data: [],
                    backgroundColor: [],
                    borderRadius: 4
                }]
            },
            options: {
                ...chartOptions,
                plugins: {legend: {display: false}}
            }
        });

    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            Object.values(charts).forEach(chart => {
                if (chart && chart.resize) chart.resize();
            });
            // Polling loops skip their tick entirely while the tab is hidden (see
            // their setInterval callbacks and loadBackgroundJobs) to avoid hammering
            // the app/target DB from a backgrounded tab — catch up immediately
            // instead of waiting for the next tick so data isn't stale on return.
            refreshAll();
            loadBackgroundJobs();
        }
    });
