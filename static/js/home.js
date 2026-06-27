// ============================
    // STATE
    // ============================
    let connections = [];
    let activeConnectionId = 'prod-greenplum';
    let charts = {};
    let modalInstance = null;
    let connectionModalMode = 'create';
    let currentSegments = [];
    let currentSegmentsWarningHtml = '';
    let segmentsSortState = {column: 'segment', direction: 'asc'};
    let schemaSizesState = {page: 1, pageSize: 100, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: ''};
    let tableSizesState = {page: 1, pageSize: 100, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: ''};
    let tableSizesRequestId = 0;
    let viewsState = {page: 1, pageSize: 100, totalCount: 0, sort: 'schema_name', direction: 'asc', search: ''};
    let viewsRequestId = 0;
    let tempTablesState = {page: 1, pageSize: 100, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: ''};
    let tempTablesRequestId = 0;
    let distributionTables = [];
    let currentDistributionSegments = [];
    let currentDistributionTotalRows = 0;
    let distributionSortState = {column: 'segment_id', direction: 'asc'};
    let distributionRequestId = 0;
    const connectionApiUrl = '/connections/';
    const connectionTestApiUrl = '/connections/test/';
    const connectionDeleteApiUrl = '/connections/delete/';
    const segmentsInfoApiUrl = '/segments/info/';
    const databaseSizeApiUrl = '/databases/size/';
    const databaseOverviewApiUrl = '/databases/overview/';
    const databaseSchemasApiUrl = '/databases/schemas/';
    const tableSizesApiUrl = '/tables/sizes/';
    const viewsListApiUrl = '/views/list/';
    const tempTablesApiUrl = '/temp-tables/sizes/';
    const distributionTablesApiUrl = '/distribution/tables/';
    const distributionInfoApiUrl = '/distribution/info/';

    const defaultConnections = [
        {id: 'prod-greenplum', name: 'Production GP', host: 'gp-prod.example.com', port: 5432, database: 'postgres', user: 'gpadmin', ssl: true, status: 'online'},
        {id: 'dev-greenplum', name: 'Dev Greenplum', host: 'gp-dev.example.com', port: 5432, database: 'postgres', user: 'gpadmin', ssl: true, status: 'online'},
        {id: 'test-postgres', name: 'Test PostgreSQL', host: 'localhost', port: 5432, database: 'postgres', user: 'postgres', ssl: false, status: 'online'},
        {id: 'analytics', name: 'Analytics Cluster', host: 'analytics.example.com', port: 5432, database: 'analytics', user: 'analytics_user', ssl: true, status: 'online'}
    ];

    const pageTitles = {
        'database-overview': 'База данных <small>Размеры и структура</small>',
        'segments': 'Сегменты <small>Состояние и конфигурация</small>',
        'databases': 'Схемы <small>Размер и статистика</small>',
        'tables': 'Таблицы <small>Список и размеры таблиц</small>',
        'views': 'Представления <small>Список представлений</small>',
        'distribution': 'Распределение <small>Перекос данных</small>',
        'temp-tables': 'Временные таблицы <small>Активные временные таблицы</small>',
        'queries': 'Активные запросы <small>Долгие запросы</small>',
        'locks': 'Блокировки <small>Кто кого блокирует</small>',
        'transactions': 'Транзакции <small>Commit / Rollback</small>',
        'memory': 'Память <small>Параметры памяти</small>',
        'bloat': 'Раздувание <small>Bloat анализ</small>',
        'maintenance': 'Обслуживание <small>VACUUM / ANALYZE</small>'
    };

    // ============================
    // INIT
    // ============================
    document.addEventListener('DOMContentLoaded', function () {
        loadConnections();
        initCharts();
        refreshSegmentsForConnection();
        refreshDatabaseSizeForConnection();
        refreshDatabaseOverviewForConnection();
        initNavigation();
        initSegmentsTableSorting();
        initSchemaSizesControls();
        initTableSizesControls();
        initViewsControls();
        initTempTablesControls();
        initDistributionControls();
        modalInstance = new bootstrap.Modal(document.getElementById('connectionModal'));

        document.getElementById('menuToggle').addEventListener('click', function () {
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

    // ============================
    // CONNECTION MANAGER
    // ============================
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
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

    function renderDatabaseSize({database = '—', size_bytes: sizeBytes = 0} = {}) {
        const value = document.getElementById('databaseSizeValue');
        const unit = document.getElementById('databaseSizeUnit');
        const name = document.getElementById('databaseSizeName');
        if (!value || !unit || !name) return;
        const formatted = formatDatabaseSize(sizeBytes);
        value.textContent = formatted.value;
        unit.textContent = formatted.unit;
        name.textContent = database;
    }

    function renderDatabaseSizeWarning(message, database = '') {
        const value = document.getElementById('databaseSizeValue');
        const unit = document.getElementById('databaseSizeUnit');
        const name = document.getElementById('databaseSizeName');
        if (!value || !unit || !name) return;
        value.textContent = message;
        unit.textContent = '';
        name.textContent = database || 'Выберите подключение';
    }

    function refreshDatabaseSizeForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderDatabaseSizeWarning('—');
            return;
        }
        renderDatabaseSizeWarning('обновление...', conn.database || conn.name);
        connectionRequest(databaseSizeApiUrl, {id: conn.id})
            .then(data => renderDatabaseSize(data))
            .catch(error => renderDatabaseSizeWarning(error.message || 'ошибка', conn.database || conn.name));
    }


    function renderDatabaseOverviewWarning(message) {
        const tbody = document.getElementById('databaseOverviewTableBody');
        const memoryTbody = document.getElementById('databaseOverviewMemoryTableBody');
        const connectionTbody = document.getElementById('databaseOverviewConnectionTableBody');
        const count = document.getElementById('databaseOverviewCount');
        const memoryCount = document.getElementById('databaseOverviewMemoryCount');
        const connectionCount = document.getElementById('databaseOverviewConnectionCount');
        const name = document.getElementById('databaseOverviewName');
        const version = document.getElementById('databaseOverviewVersion');
        if (count) count.textContent = 'Нет данных';
        if (memoryCount) memoryCount.textContent = 'Нет данных';
        if (connectionCount) connectionCount.textContent = 'Нет данных';
        if (name) name.textContent = 'Выберите подключение';
        if (version) version.textContent = message;
        if (tbody) tbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
        if (memoryTbody) memoryTbody.innerHTML = `<tr><td colspan="3" class="text-muted">${message}</td></tr>`;
        if (connectionTbody) connectionTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
    }

    function renderDatabaseOverview(data) {
        const tbody = document.getElementById('databaseOverviewTableBody');
        const memoryTbody = document.getElementById('databaseOverviewMemoryTableBody');
        const connectionTbody = document.getElementById('databaseOverviewConnectionTableBody');
        const count = document.getElementById('databaseOverviewCount');
        const memoryCount = document.getElementById('databaseOverviewMemoryCount');
        const connectionCount = document.getElementById('databaseOverviewConnectionCount');
        const name = document.getElementById('databaseOverviewName');
        const version = document.getElementById('databaseOverviewVersion');
        const metrics = data.metrics || [];
        const memorySettings = data.memory_settings || [];
        const connectionInfo = data.connection_info || [];
        if (count) count.textContent = `${metrics.length} метрик`;
        if (memoryCount) memoryCount.textContent = `${memorySettings.length} параметра`;
        if (connectionCount) connectionCount.textContent = `${connectionInfo.length} параметров`;
        if (name) name.textContent = data.database || '—';
        if (version) version.textContent = data.database_version || '—';
        if (connectionTbody) {
            if (!connectionInfo.length) {
                connectionTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных о подключении</td></tr>';
            } else {
                connectionTbody.innerHTML = connectionInfo.map(item => `
                    <tr>
                        <td>${item.label}</td>
                        <td><strong>${item.value ?? '—'}</strong></td>
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
                            <td>${item.label}</td>
                            <td><strong>${formatted.value} ${formatted.unit}</strong></td>
                        </tr>
                    `;
                }).join('');
            }
        }
        if (memoryTbody) {
            if (!memorySettings.length) {
                memoryTbody.innerHTML = '<tr><td colspan="3" class="text-muted">Нет данных о параметрах памяти</td></tr>';
            } else {
                memoryTbody.innerHTML = memorySettings.map(item => `
                    <tr>
                        <td><code>${item.setting}</code></td>
                        <td>${item.label}</td>
                        <td><strong>${item.value}</strong></td>
                    </tr>
                `).join('');
            }
        }
    }

    function refreshDatabaseOverviewForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderDatabaseOverviewWarning('Выберите сохранённое подключение для загрузки размеров БД');
            return;
        }
        renderDatabaseOverviewWarning('Загрузка размеров БД...');
        connectionRequest(databaseOverviewApiUrl, {id: conn.id})
            .then(data => renderDatabaseOverview(data))
            .catch(error => renderDatabaseOverviewWarning(error.message || 'Не удалось получить размеры БД'));
    }

    function renderSchemaSizesWarning(message) {
        const tbody = document.getElementById('schemaSizesTableBody');
        const count = document.getElementById('schemaSizesCount');
        const info = document.getElementById('schemaPaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="3" class="text-muted">${message}</td></tr>`;
        }
        updateSchemaPaginationButtons();
    }

    function updateSchemaSortIndicators() {
        document.querySelectorAll('[data-schema-sort]').forEach(button => {
            const icon = button.querySelector('i');
            const isActive = button.dataset.schemaSort === schemaSizesState.sort;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${schemaSizesState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function updateSchemaPaginationButtons() {
        const totalPages = Math.max(Math.ceil(schemaSizesState.totalCount / schemaSizesState.pageSize), 1);
        const prev = document.getElementById('schemaPrevPageBtn');
        const next = document.getElementById('schemaNextPageBtn');
        if (prev) prev.disabled = schemaSizesState.page <= 1;
        if (next) next.disabled = schemaSizesState.page >= totalPages;
    }

    function renderSchemaSizes(data) {
        const tbody = document.getElementById('schemaSizesTableBody');
        const count = document.getElementById('schemaSizesCount');
        const info = document.getElementById('schemaPaginationInfo');
        if (!tbody) return;
        schemaSizesState.totalCount = Number(data.total_count) || 0;
        schemaSizesState.page = Number(data.page) || 1;
        schemaSizesState.pageSize = Number(data.page_size) || 100;
        updateSchemaSortIndicators();
        const totalPages = Math.max(Math.ceil(schemaSizesState.totalCount / schemaSizesState.pageSize), 1);
        if (count) count.textContent = `${data.schemas?.length || 0} из ${schemaSizesState.totalCount} схем`;
        if (info) info.textContent = `Страница ${schemaSizesState.page} из ${totalPages}`;
        if (!data.schemas?.length) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-muted">Схемы не найдены</td></tr>';
            updateSchemaPaginationButtons();
            return;
        }
        tbody.innerHTML = data.schemas.map(schema => `
            <tr>
                <td><strong>${schema.schema_name || '-'}</strong></td>
                <td>${schema.schema_owner || '-'}</td>
                <td>${schema.table_size || formatDatabaseSize(schema.size_bytes).value + ' ' + formatDatabaseSize(schema.size_bytes).unit}</td>
            </tr>
        `).join('');
        updateSchemaPaginationButtons();
    }

    function initSchemaSizesControls() {
        let searchTimer = null;
        document.getElementById('schemaSearchInput')?.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                schemaSizesState.search = this.value.trim();
                schemaSizesState.page = 1;
                refreshSchemaSizesForConnection();
            }, 300);
        });
        document.querySelectorAll('[data-schema-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.schemaSort;
                if (schemaSizesState.sort === sort) {
                    schemaSizesState.direction = schemaSizesState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    schemaSizesState.sort = sort;
                    schemaSizesState.direction = sort === 'size_bytes' ? 'desc' : 'asc';
                }
                schemaSizesState.page = 1;
                refreshSchemaSizesForConnection();
            });
        });
        document.getElementById('schemaPrevPageBtn')?.addEventListener('click', function () {
            if (schemaSizesState.page > 1) {
                schemaSizesState.page -= 1;
                refreshSchemaSizesForConnection();
            }
        });
        document.getElementById('schemaNextPageBtn')?.addEventListener('click', function () {
            const totalPages = Math.max(Math.ceil(schemaSizesState.totalCount / schemaSizesState.pageSize), 1);
            if (schemaSizesState.page < totalPages) {
                schemaSizesState.page += 1;
                refreshSchemaSizesForConnection();
            }
        });
        updateSchemaSortIndicators();
        updateSchemaPaginationButtons();
    }

    function refreshSchemaSizesForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            schemaSizesState.totalCount = 0;
            renderSchemaSizesWarning('Выберите сохранённое подключение для загрузки размеров схем');
            return;
        }
        renderSchemaSizesWarning('Загрузка размеров схем...');
        connectionRequest(databaseSchemasApiUrl, {
            id: conn.id,
            page: schemaSizesState.page,
            search: schemaSizesState.search,
            sort: schemaSizesState.sort,
            direction: schemaSizesState.direction
        })
            .then(data => renderSchemaSizes(data))
            .catch(error => {
                schemaSizesState.totalCount = 0;
                renderSchemaSizesWarning(error.message || 'Не удалось получить размеры схем');
            });
    }


    function formatRowCount(value) {
        const number = Number(value) || 0;
        return new Intl.NumberFormat('ru-RU').format(number);
    }

    function renderTableSizesWarning(message) {
        const tbody = document.getElementById('tableSizesTableBody');
        const count = document.getElementById('tableSizesCount');
        const info = document.getElementById('tablePaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-muted">${message}</td></tr>`;
        updateTablePaginationButtons();
    }

    function updateTableSortIndicators() {
        document.querySelectorAll('[data-table-sort]').forEach(button => {
            const icon = button.querySelector('i');
            const isActive = button.dataset.tableSort === tableSizesState.sort;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${tableSizesState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function updateTablePaginationButtons() {
        const totalPages = Math.max(Math.ceil(tableSizesState.totalCount / tableSizesState.pageSize), 1);
        const prev = document.getElementById('tablePrevPageBtn');
        const next = document.getElementById('tableNextPageBtn');
        if (prev) prev.disabled = tableSizesState.page <= 1;
        if (next) next.disabled = tableSizesState.page >= totalPages;
    }

    function renderTableSizes(data) {
        const tbody = document.getElementById('tableSizesTableBody');
        const count = document.getElementById('tableSizesCount');
        const info = document.getElementById('tablePaginationInfo');
        if (!tbody) return;
        tableSizesState.totalCount = Number(data.total_count) || 0;
        tableSizesState.page = Number(data.page) || 1;
        tableSizesState.pageSize = Number(data.page_size) || 100;
        updateTableSortIndicators();
        const totalPages = Math.max(Math.ceil(tableSizesState.totalCount / tableSizesState.pageSize), 1);
        if (count) count.textContent = `${data.tables?.length || 0} из ${tableSizesState.totalCount} таблиц`;
        if (info) info.textContent = `Страница ${tableSizesState.page} из ${totalPages}`;
        if (!data.tables?.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Таблицы не найдены</td></tr>';
            updateTablePaginationButtons();
            return;
        }
        tbody.innerHTML = data.tables.map(table => `
            <tr>
                <td>${table.schema_name || '-'}</td>
                <td><strong>${table.table_name || '-'}</strong></td>
                <td>${table.table_owner || '-'}</td>
                <td>${table.table_size || '-'}</td>
                <td>${table.index_size || '-'}</td>
                <td>${formatRowCount(table.index_count)}</td>
                <td>${formatRowCount(table.row_count)}</td>
            </tr>
        `).join('');
        updateTablePaginationButtons();
    }

    function refreshTableSizesForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        const requestId = ++tableSizesRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderTableSizesWarning('Выберите сохранённое подключение для загрузки размеров таблиц');
            return;
        }
        renderTableSizesWarning('Загрузка размеров таблиц...');
        connectionRequest(tableSizesApiUrl, {
            id: conn.id,
            page: tableSizesState.page,
            search: tableSizesState.search,
            sort: tableSizesState.sort,
            direction: tableSizesState.direction
        })
            .then(data => {
                if (requestId === tableSizesRequestId) renderTableSizes(data);
            })
            .catch(error => {
                if (requestId === tableSizesRequestId) {
                    renderTableSizesWarning(error.message || 'Не удалось получить размеры таблиц');
                }
            });
    }

    function initTableSizesControls() {
        let searchTimer = null;
        document.getElementById('tableSearchInput')?.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                tableSizesState.search = this.value.trim();
                tableSizesState.page = 1;
                refreshTableSizesForConnection();
            }, 300);
        });
        document.querySelectorAll('[data-table-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.tableSort;
                if (tableSizesState.sort === sort) {
                    tableSizesState.direction = tableSizesState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    tableSizesState.sort = sort;
                    tableSizesState.direction = ['size_bytes', 'index_size_bytes', 'index_count', 'row_count'].includes(sort) ? 'desc' : 'asc';
                }
                tableSizesState.page = 1;
                refreshTableSizesForConnection();
            });
        });
        document.getElementById('tablePrevPageBtn')?.addEventListener('click', function () {
            if (tableSizesState.page > 1) {
                tableSizesState.page -= 1;
                refreshTableSizesForConnection();
            }
        });
        document.getElementById('tableNextPageBtn')?.addEventListener('click', function () {
            const totalPages = Math.max(Math.ceil(tableSizesState.totalCount / tableSizesState.pageSize), 1);
            if (tableSizesState.page < totalPages) {
                tableSizesState.page += 1;
                refreshTableSizesForConnection();
            }
        });
        updateTableSortIndicators();
        updateTablePaginationButtons();
    }

    function renderViewsWarning(message) {
        const tbody = document.getElementById('viewsTableBody');
        const count = document.getElementById('viewsCount');
        const info = document.getElementById('viewPaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-muted">${message}</td></tr>`;
        updateViewPaginationButtons();
    }

    function updateViewSortIndicators() {
        document.querySelectorAll('[data-view-sort]').forEach(button => {
            const icon = button.querySelector('i');
            const isActive = button.dataset.viewSort === viewsState.sort;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${viewsState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function updateViewPaginationButtons() {
        const totalPages = Math.max(Math.ceil(viewsState.totalCount / viewsState.pageSize), 1);
        const prev = document.getElementById('viewPrevPageBtn');
        const next = document.getElementById('viewNextPageBtn');
        if (prev) prev.disabled = viewsState.page <= 1;
        if (next) next.disabled = viewsState.page >= totalPages;
    }

    function renderViews(data) {
        const tbody = document.getElementById('viewsTableBody');
        const count = document.getElementById('viewsCount');
        const info = document.getElementById('viewPaginationInfo');
        if (!tbody) return;
        viewsState.totalCount = Number(data.total_count) || 0;
        viewsState.page = Number(data.page) || 1;
        viewsState.pageSize = Number(data.page_size) || 100;
        updateViewSortIndicators();
        const totalPages = Math.max(Math.ceil(viewsState.totalCount / viewsState.pageSize), 1);
        if (count) count.textContent = `${data.views?.length || 0} из ${viewsState.totalCount} представлений`;
        if (info) info.textContent = `Страница ${viewsState.page} из ${totalPages}`;
        if (!data.views?.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Представления не найдены</td></tr>';
            updateViewPaginationButtons();
            return;
        }
        tbody.innerHTML = data.views.map(view => `
            <tr>
                <td>${view.schema_name || '-'}</td>
                <td><strong>${view.view_name || '-'}</strong></td>
                <td>${view.view_owner || '-'}</td>
                <td>${view.view_type || '-'}</td>
                <td>${view.view_size || '-'}</td>
                <td>${view.index_size || '-'}</td>
                <td>${formatRowCount(view.row_count)}</td>
            </tr>
        `).join('');
        updateViewPaginationButtons();
    }

    function refreshViewsForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        const requestId = ++viewsRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderViewsWarning('Выберите сохранённое подключение для загрузки представлений');
            return;
        }
        renderViewsWarning('Загрузка представлений...');
        connectionRequest(viewsListApiUrl, {
            id: conn.id,
            page: viewsState.page,
            search: viewsState.search,
            sort: viewsState.sort,
            direction: viewsState.direction
        })
            .then(data => {
                if (requestId === viewsRequestId) renderViews(data);
            })
            .catch(error => {
                if (requestId === viewsRequestId) {
                    renderViewsWarning(error.message || 'Не удалось получить представления');
                }
            });
    }

    function initViewsControls() {
        let searchTimer = null;
        document.getElementById('viewSearchInput')?.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                viewsState.search = this.value.trim();
                viewsState.page = 1;
                refreshViewsForConnection();
            }, 300);
        });
        document.querySelectorAll('[data-view-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.viewSort;
                if (viewsState.sort === sort) {
                    viewsState.direction = viewsState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    viewsState.sort = sort;
                    viewsState.direction = ['size_bytes', 'index_size_bytes', 'row_count'].includes(sort) ? 'desc' : 'asc';
                }
                viewsState.page = 1;
                refreshViewsForConnection();
            });
        });
        document.getElementById('viewPrevPageBtn')?.addEventListener('click', function () {
            if (viewsState.page > 1) {
                viewsState.page -= 1;
                refreshViewsForConnection();
            }
        });
        document.getElementById('viewNextPageBtn')?.addEventListener('click', function () {
            const totalPages = Math.max(Math.ceil(viewsState.totalCount / viewsState.pageSize), 1);
            if (viewsState.page < totalPages) {
                viewsState.page += 1;
                refreshViewsForConnection();
            }
        });
        updateViewSortIndicators();
        updateViewPaginationButtons();
    }

    function renderDistributionWarning(message) {
        currentDistributionSegments = [];
        currentDistributionTotalRows = 0;
        const tbody = document.getElementById('distributionTableBody');
        const count = document.getElementById('distributionRowsCount');
        const tableName = document.getElementById('distributionSelectedTableName');
        if (count) count.textContent = 'Нет данных';
        if (tableName) tableName.textContent = 'Выберите таблицу';
        if (tbody) tbody.innerHTML = `<tr><td colspan="3" class="text-muted">${message}</td></tr>`;
        updateDistributionMetrics();
        updateSegmentDistributionChart([]);
    }

    function updateDistributionMetrics(metrics = {}) {
        const ratio = document.getElementById('distributionSkewRatio');
        const total = document.getElementById('distributionTotalRows');
        const status = document.getElementById('distributionStatus');
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
            const icon = button.querySelector('i');
            const isActive = button.dataset.distributionSort === distributionSortState.column;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${distributionSortState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
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

    function refreshDistributionForSelectedTable() {
        const select = document.getElementById('distributionTableSelect');
        const selectedIndex = Number(select?.value);
        const selectedTable = Number.isInteger(selectedIndex) ? distributionTables[selectedIndex] : null;
        const requestId = ++distributionRequestId;
        if (!selectedTable) {
            renderDistributionWarning('Выберите таблицу для расчёта распределения');
            return;
        }
        const {schema_name: schemaName, table_name: tableName} = selectedTable;
        const conn = connections.find(c => c.id === activeConnectionId);
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
            select.innerHTML = '<option value="">Таблицы не найдены</option>';
            renderDistributionWarning('Таблицы не найдены');
            return;
        }
        select.innerHTML = tables.map((table, index) => `<option value="${index}">${table.schema_name}.${table.table_name} — ${table.object_type || 'Таблица'}</option>`).join('');
        refreshDistributionForSelectedTable();
    }

    function refreshDistributionTablesForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        const select = document.getElementById('distributionTableSelect');
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            distributionTables = [];
            if (select) select.innerHTML = '<option value="">Выберите сохранённое подключение для загрузки таблиц</option>';
            renderDistributionWarning('Выберите сохранённое подключение для загрузки списка таблиц');
            return;
        }
        if (select) select.innerHTML = '<option value="">Загрузка таблиц...</option>';
        connectionRequest(distributionTablesApiUrl, {id: conn.id})
            .then(data => {
                distributionTables = data.tables || [];
                renderDistributionTableOptions(distributionTables);
            })
            .catch(error => {
                distributionTables = [];
                if (select) select.innerHTML = '<option value="">Не удалось загрузить таблицы</option>';
                renderDistributionWarning(error.message || 'Не удалось загрузить список таблиц');
            });
    }

    function initDistributionControls() {
        document.getElementById('distributionTableSelect')?.addEventListener('change', refreshDistributionForSelectedTable);
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

    function renderTempTablesWarning(message) {
        const tbody = document.getElementById('tempTablesTableBody');
        const count = document.getElementById('tempTablesCount');
        const info = document.getElementById('tempTablePaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-muted">${message}</td></tr>`;
        updateTempTablePaginationButtons();
    }

    function updateTempTableSortIndicators() {
        document.querySelectorAll('[data-temp-table-sort]').forEach(button => {
            const icon = button.querySelector('i');
            const isActive = button.dataset.tempTableSort === tempTablesState.sort;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${tempTablesState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function updateTempTablePaginationButtons() {
        const totalPages = Math.max(Math.ceil(tempTablesState.totalCount / tempTablesState.pageSize), 1);
        const prev = document.getElementById('tempTablePrevPageBtn');
        const next = document.getElementById('tempTableNextPageBtn');
        if (prev) prev.disabled = tempTablesState.page <= 1;
        if (next) next.disabled = tempTablesState.page >= totalPages;
    }

    function renderTempTables(data) {
        const tbody = document.getElementById('tempTablesTableBody');
        const count = document.getElementById('tempTablesCount');
        const info = document.getElementById('tempTablePaginationInfo');
        if (!tbody) return;
        tempTablesState.totalCount = Number(data.total_count) || 0;
        tempTablesState.page = Number(data.page) || 1;
        tempTablesState.pageSize = Number(data.page_size) || 100;
        updateTempTableSortIndicators();
        const totalPages = Math.max(Math.ceil(tempTablesState.totalCount / tempTablesState.pageSize), 1);
        if (count) count.textContent = `${data.temp_tables?.length || 0} из ${tempTablesState.totalCount} временных таблиц`;
        if (info) info.textContent = `Страница ${tempTablesState.page} из ${totalPages}`;
        if (!data.temp_tables?.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Временные таблицы не найдены</td></tr>';
            updateTempTablePaginationButtons();
            return;
        }
        tbody.innerHTML = data.temp_tables.map(table => `
            <tr>
                <td>${table.schema_name || '-'}</td>
                <td><strong>${table.table_name || '-'}</strong></td>
                <td>${table.table_owner || '-'}</td>
                <td>${table.table_size || '-'}</td>
            </tr>
        `).join('');
        updateTempTablePaginationButtons();
    }

    function refreshTempTablesForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        const requestId = ++tempTablesRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderTempTablesWarning('Выберите сохранённое подключение для загрузки временных таблиц');
            return;
        }
        renderTempTablesWarning('Загрузка временных таблиц...');
        connectionRequest(tempTablesApiUrl, {
            id: conn.id,
            page: tempTablesState.page,
            search: tempTablesState.search,
            sort: tempTablesState.sort,
            direction: tempTablesState.direction
        })
            .then(data => {
                if (requestId === tempTablesRequestId) renderTempTables(data);
            })
            .catch(error => {
                if (requestId === tempTablesRequestId) {
                    renderTempTablesWarning(error.message || 'Не удалось получить временные таблицы');
                }
            });
    }

    function initTempTablesControls() {
        let searchTimer = null;
        document.getElementById('tempTableSearchInput')?.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                tempTablesState.search = this.value.trim();
                tempTablesState.page = 1;
                refreshTempTablesForConnection();
            }, 300);
        });
        document.querySelectorAll('[data-temp-table-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.tempTableSort;
                if (tempTablesState.sort === sort) {
                    tempTablesState.direction = tempTablesState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    tempTablesState.sort = sort;
                    tempTablesState.direction = sort === 'size_bytes' ? 'desc' : 'asc';
                }
                tempTablesState.page = 1;
                refreshTempTablesForConnection();
            });
        });
        document.getElementById('tempTablePrevPageBtn')?.addEventListener('click', function () {
            if (tempTablesState.page > 1) {
                tempTablesState.page -= 1;
                refreshTempTablesForConnection();
            }
        });
        document.getElementById('tempTableNextPageBtn')?.addEventListener('click', function () {
            const totalPages = Math.max(Math.ceil(tempTablesState.totalCount / tempTablesState.pageSize), 1);
            if (tempTablesState.page < totalPages) {
                tempTablesState.page += 1;
                refreshTempTablesForConnection();
            }
        });
        updateTempTableSortIndicators();
        updateTempTablePaginationButtons();
    }

    function connectionRequest(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
        }).then(async response => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.ok === false) {
                throw new Error(data.message || 'Ошибка запроса');
            }
            return data;
        });
    }

    function loadConnections() {
        fetch(connectionApiUrl)
            .then(response => response.json())
            .then(data => {
                connections = data.connections || [];
                if (connections.length === 0) {
                    connections = [...defaultConnections];
                }
                activeConnectionId = connections[0]?.id || activeConnectionId;
                populateConnectionSelect();
                refreshSegmentsForConnection();
            })
            .catch(() => {
                const saved = localStorage.getItem('gp_connections');
                if (saved) {
                    try {
                        connections = JSON.parse(saved);
                    } catch (e) {
                        connections = [...defaultConnections];
                    }
                } else {
                    connections = [...defaultConnections];
                }
                activeConnectionId = connections[0]?.id || activeConnectionId;
                populateConnectionSelect();
                refreshSegmentsForConnection();
                showToast('⚠️ Не удалось загрузить подключения из БД, используется локальный список');
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
            const icon = button.querySelector('i');
            const isActive = button.dataset.segmentsSort === segmentsSortState.column;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${segmentsSortState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
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
                <div class="metric-name">${metric.name}</div>
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
                <td><strong>${segment.segment}</strong></td>
                <td>${roleLabel(segment.role)}</td>
                <td>${statusBadge(segment.status)}</td>
                <td>${modeBadge(segment.mode)}</td>
                <td>${segment.hostname || segment.address || '-'}</td>
            </tr>
        `).join('');
    }

    function updateSegmentsChart(segments) {
        if (!charts.segments) return;
        const contents = [...new Set(segments.filter(segment => Number(segment.segment) >= 0).map(segment => String(segment.segment)))].sort((a, b) => Number(a) - Number(b));
        charts.segments.data.labels = contents.map(content => `Сегмент ${content}`);
        charts.segments.data.datasets[0].data = contents.map(content => segments.filter(segment => String(segment.segment) === content && segment.role === 'p').length);
        charts.segments.data.datasets[1].data = contents.map(content => segments.filter(segment => String(segment.segment) === content && segment.role === 'm').length);
        charts.segments.update();
    }

    function formatSegmentError(message) {
        const normalized = String(message || '').replace(/\s+/g, ' ').trim();
        if (normalized.includes('gp_segment_configuration') || normalized.includes('не существует')) {
            return {
                title: 'Сегменты недоступны для выбранного подключения',
                text: 'Выбранное подключение не похоже на Greenplum или у пользователя нет доступа к gp_segment_configuration. Выберите Greenplum-подключение или проверьте права доступа.'
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
                    <strong>${warning.title}</strong>
                    <span>${warning.text}</span>
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

    function refreshSegmentsForConnection(conn = connections.find(c => c.id === activeConnectionId)) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderSegmentsWarning('Информация о сегментах недоступна: выберите сохранённое подключение Greenplum.');
            return;
        }

        const badge = document.getElementById('segmentHealthBadge');
        if (badge) {
            badge.className = 'badge badge-soft-info';
            badge.textContent = 'Обновление...';
        }

        connectionRequest(segmentsInfoApiUrl, {id: conn.id})
            .then(data => renderSegmentsInfo(data))
            .catch(error => renderSegmentsWarning(error.message || 'Информация о сегментах недоступна для выбранного подключения.'));
    }

    function saveConnections() {
        localStorage.setItem('gp_connections', JSON.stringify(connections));
    }

    function populateConnectionSelect() {
        const select = document.getElementById('connectionSelect');
        select.innerHTML = '';
        connections.forEach(conn => {
            const option = document.createElement('option');
            option.value = conn.id;
            const activityMarker = conn.status === 'online' ? '🟢' : '🔴';
            option.textContent = `${activityMarker} ${conn.name}`;
            select.appendChild(option);
        });
        if (activeConnectionId) {
            select.value = activeConnectionId;
        }
    }

    function activatePage(pageId) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === pageId);
        });
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        const target = document.getElementById('page-' + pageId);
        if (target) target.classList.add('active');
        document.getElementById('pageTitle').innerHTML = pageTitles[pageId] || pageId;

        if (pageId === 'database-overview') {
            refreshDatabaseOverviewForConnection();
        }
        if (pageId === 'databases') {
            refreshDatabaseSizeForConnection();
            refreshSchemaSizesForConnection();
        }
        if (pageId === 'tables') {
            refreshTableSizesForConnection();
        }
        if (pageId === 'views') {
            refreshViewsForConnection();
        }
        if (pageId === 'temp-tables') {
            refreshTempTablesForConnection();
        }
        if (pageId === 'distribution') {
            refreshDistributionTablesForConnection();
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
        const conn = connections.find(c => c.id === connId);
        if (conn) {
            activatePage('segments');
            refreshSegmentsForConnection(conn);
            refreshDatabaseSizeForConnection(conn);
            showToast(`🔌 Подключено к ${conn.name}`);
            refreshAll();
        }
    }

    function openConnectionModal() {
        connectionModalMode = 'create';
        document.getElementById('connectionModalTitle').innerHTML = '<i class="fas fa-plug me-2" style="color: var(--accent-blue);"></i>Новое подключение';
        document.getElementById('connectionSaveText').textContent = 'Подключиться';
        document.getElementById('connectionDeleteBtn').classList.add('d-none');
        document.getElementById('connId').value = '';
        modalInstance.show();
        document.getElementById('connName').value = 'New Connection';
        document.getElementById('connHost').value = 'localhost';
        document.getElementById('connPort').value = '5432';
        document.getElementById('connDatabase').value = 'postgres';
        document.getElementById('connUser').value = 'postgres';
        document.getElementById('connDbType').value = 'PostgreSQL';
        document.getElementById('connPassword').value = '';
    }

    function editConnection() {
        const conn = connections.find(c => c.id === activeConnectionId);
        if (!conn) {
            showToast('⚠️ Подключение не выбрано');
            return;
        }

        connectionModalMode = 'edit';
        document.getElementById('connectionModalTitle').innerHTML = '<i class="fas fa-pen me-2" style="color: var(--accent-blue);"></i>Редактировать подключение';
        document.getElementById('connectionSaveText').textContent = 'Сохранить';
        document.getElementById('connectionDeleteBtn').classList.remove('d-none');
        document.getElementById('connId').value = /^\d+$/.test(String(conn.id)) ? conn.id : '';
        document.getElementById('connName').value = conn.name || '';
        document.getElementById('connHost').value = conn.host || 'localhost';
        document.getElementById('connPort').value = conn.port || '5432';
        document.getElementById('connDatabase').value = conn.database || 'postgres';
        document.getElementById('connUser').value = conn.user || 'postgres';
        document.getElementById('connDbType').value = conn.db_type || 'PostgreSQL';
        document.getElementById('connPassword').value = '';
        modalInstance.show();
    }

    function deleteConnection() {
        const payload = getConnectionFormData();
        const conn = connections.find(c => c.id === activeConnectionId);
        if (!conn) {
            showToast('⚠️ Подключение не выбрано');
            return;
        }

        if (!confirm(`Удалить подключение "${conn.name}"?`)) {
            return;
        }

        const finishDelete = message => {
            connections = connections.filter(item => item.id !== activeConnectionId);
            activeConnectionId = connections[0]?.id || null;
            saveConnections();
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
                const existingIndex = connections.findIndex(conn => conn.id === savedConnection.id || (connectionModalMode === 'edit' && conn.id === activeConnectionId));
                if (existingIndex >= 0) {
                    connections[existingIndex] = savedConnection;
                } else {
                    connections.push(savedConnection);
                }
                saveConnections();
                populateConnectionSelect();

                document.getElementById('connectionSelect').value = savedConnection.id;
                activeConnectionId = savedConnection.id;
                refreshSegmentsForConnection(savedConnection);
                refreshDatabaseSizeForConnection(savedConnection);
                modalInstance.hide();
                showToast(`✅ Подключение "${savedConnection.name}" проверено и сохранено`);
                refreshAll();
            })
            .catch(error => showToast(`❌ ${error.message}`));
    }

    function testNewConnection() {
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
        const conn = connections.find(c => c.id === activeConnectionId);
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
                saveConnections();
                populateConnectionSelect();
                document.getElementById('connectionSelect').value = activeConnectionId;
                showToast(`✅ ${data.message}`);
            })
            .catch(error => {
                conn.status = 'offline';
                saveConnections();
                populateConnectionSelect();
                document.getElementById('connectionSelect').value = activeConnectionId;
                showToast(`❌ ${error.message}`);
            });
    }

    // ============================
    // NAVIGATION
    // ============================
    function initNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
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
        document.getElementById('toastMessage').textContent = message;
        const toast = new bootstrap.Toast(document.getElementById('liveToast'));
        toast.show();
    }

    // ============================
    // REFRESH
    // ============================
    function refreshAll() {
        if (document.getElementById('page-database-overview')?.classList.contains('active')) {
            refreshDatabaseOverviewForConnection();
        }
        if (document.getElementById('page-databases')?.classList.contains('active')) {
            refreshDatabaseSizeForConnection();
            refreshSchemaSizesForConnection();
        }
        if (document.getElementById('page-tables')?.classList.contains('active')) {
            refreshTableSizesForConnection();
        }
        if (document.getElementById('page-views')?.classList.contains('active')) {
            refreshViewsForConnection();
        }
        if (document.getElementById('page-temp-tables')?.classList.contains('active')) {
            refreshTempTablesForConnection();
        }
        if (document.getElementById('page-distribution')?.classList.contains('active')) {
            refreshDistributionTablesForConnection();
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
                labels: ['Сегмент 0', 'Сегмент 1', 'Сегмент 2', 'Сегмент 3', 'Сегмент 4', 'Сегмент 5'],
                datasets: [
                    {label: 'Primary', data: [1, 1, 1, 1, 1, 1], backgroundColor: colors.blue},
                    {label: 'Mirror', data: [1, 1, 1, 1, 1, 1], backgroundColor: colors.teal}
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
                    label: 'Строк',
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

        // ---- 10. Transactions ----
        const ctx10 = document.getElementById('txChart').getContext('2d');
        charts.tx = new Chart(ctx10, {
            type: 'bar',
            data: {
                labels: ['dd04_finance', 'dwh_cube', 'dc00_sys', 'postgres'],
                datasets: [
                    {label: 'Коммиты (тыс)', data: [2345.7, 1876.5, 987.7, 45.7], backgroundColor: colors.green, borderRadius: 4},
                    {label: 'Роллбеки (тыс)', data: [45.2, 123.5, 12.3, 1.2], backgroundColor: colors.red, borderRadius: 4}
                ]
            },
            options: chartOptions
        });

        // ---- 11. Rollback ----
        const ctx11 = document.getElementById('rollbackChart').getContext('2d');
        charts.rollback = new Chart(ctx11, {
            type: 'bar',
            data: {
                labels: ['dd04_finance', 'dwh_cube', 'dc00_sys', 'postgres'],
                datasets: [{
                    label: 'Rollback %',
                    data: [1.89, 6.17, 1.23, 2.63],
                    backgroundColor: [colors.green, colors.yellow, colors.green, colors.green],
                    borderRadius: 4
                }]
            },
            options: {
                ...chartOptions,
                plugins: {legend: {display: false}}
            }
        });

        // ---- 12. Bloat ----
        const ctx12 = document.getElementById('bloatChart').getContext('2d');
        charts.bloat = new Chart(ctx12, {
            type: 'bar',
            data: {
                labels: ['dd04443_bal', 'fact_sales', 'dd04443_tx', 'dc00006_audit', 'dim_customer'],
                datasets: [{
                    label: 'Процент вздутия',
                    data: [28.5, 18.2, 14.7, 8.3, 5.1],
                    backgroundColor: [colors.red, colors.yellow, colors.yellow, colors.green, colors.green],
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
        }
    });
