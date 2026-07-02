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
    let schemaSizesState = {page: 1, pageSize: 100, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: ''};
    let tableSizesState = {page: 1, pageSize: 100, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: ''};
    let tableSizesRequestId = 0;
    let viewsState = {page: 1, pageSize: 100, totalCount: 0, sort: 'schema_name', direction: 'asc', search: '', viewType: ''};
    let viewsRequestId = 0;
    let tempTablesState = {page: 1, pageSize: 100, totalCount: 0, sort: 'size_bytes', direction: 'desc', search: ''};
    let tempTablesRequestId = 0;
    let distributionTables = [];
    let currentDistributionSegments = [];
    let currentDistributionTotalRows = 0;
    let distributionSortState = {column: 'segment_id', direction: 'asc'};
    let distributionRequestId = 0;
    let activeQueriesRequestId = 0;
    let activeQueriesState = {sort: 'duration_seconds', direction: 'desc', refreshInterval: 0, timer: null};
    let blockingLocksRequestId = 0;
    let blockingLocksState = {refreshInterval: 0, timer: null};
    let idleTransactionsRequestId = 0;
    let idleTransactionsState = {refreshInterval: 0, timer: null};
    let maintenanceStatsState = {page: 1, pageSize: 100, totalCount: 0, sort: 'dead_rows', direction: 'desc', search: '', selectedTableKey: ''};
    let maintenanceStatsRequestId = 0;
    let usersState = {page: 1, pageSize: 100, totalCount: 0, sort: 'name', direction: 'asc', search: ''};
    let usersRequestId = 0;
    let groupsState = {sort: 'name', direction: 'asc', search: ''};
    let groupsRequestId = 0;
    const activePageStorageKey = 'gp_active_page';
    const activeConnectionStorageKey = 'gp_active_connection';
    const sidebarCollapsedStorageKey = 'gp_sidebar_collapsed';
    const tableChartCollapsedStorageKey = 'gp_table_chart_collapsed';
    const connectionApiUrl = '/connections/';
    const connectionTestApiUrl = '/connections/test/';
    const connectionDeleteApiUrl = '/connections/delete/';
    const segmentsInfoApiUrl = '/segments/info/';
    const databaseOverviewApiUrl = '/databases/overview/';
    const databaseSchemasApiUrl = '/databases/schemas/';
    const tableSizesApiUrl = '/tables/sizes/';
    const viewsListApiUrl = '/views/list/';
    const tempTablesApiUrl = '/temp-tables/sizes/';
    const distributionTablesApiUrl = '/distribution/tables/';
    const distributionInfoApiUrl = '/distribution/info/';
    const activeQueriesApiUrl = '/queries/active/';
    const blockingLocksApiUrl = '/locks/blocking/';
    const idleTransactionsApiUrl = '/transactions/idle/';
    const memoryOverviewApiUrl = '/memory/overview/';
    const maintenanceStatsApiUrl = '/maintenance/stats/';
    const usersListApiUrl = '/users/list/';
    const groupsListApiUrl = '/groups/list/';

    const pageTitles = {
        'home': 'Главная <small>Описание разделов</small>',
        'database-overview': 'База данных <small>Размеры и структура</small>',
        'segments': 'Сегменты <small>Состояние и конфигурация</small>',
        'databases': 'Схемы <small>Список схем</small>',
        'tables': 'Таблицы <small>Список таблиц</small>',
        'views': 'Представления <small>Список представлений</small>',
        'distribution': 'Распределение <small>Перекос данных</small>',
        'temp-tables': 'Временные таблицы <small>Активные временные таблицы</small>',
        'queries': 'Активные запросы <small>Долгие запросы</small>',
        'locks': 'Блокировки <small>Кто кого блокирует</small>',
        'transactions': 'Транзакции <small>Commit / Rollback</small>',
        'memory': 'Память <small>Параметры памяти</small>',
        'users': 'Пользователи <small>Список пользователей</small>',
        'groups': 'Группы <small>Список групп</small>',
        'maintenance': 'Обслуживание <small>Очистка / анализ</small>'
    };


    const greenplumOnlyPages = new Set(['segments', 'distribution']);

    function isPostgreSQLConnection(conn) {
        return String(conn?.db_type || '').toLowerCase() === 'postgresql';
    }

    function isPageAvailableForConnection(pageId, conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        if (!pageId) return false;
        if (isPostgreSQLConnection(conn) && greenplumOnlyPages.has(pageId)) return false;
        return true;
    }

    function getDefaultPageForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        return isPostgreSQLConnection(conn) ? 'database-overview' : 'segments';
    }

    function updateSidebarForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        document.querySelectorAll('.nav-item').forEach(item => {
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

    function canManageConnections() {
        return currentDbUser?.can_manage_connections === true;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // ============================
    // INIT
    // ============================
    document.addEventListener('DOMContentLoaded', function () {
        loadConnections();
        initCharts();
        initNavigation();
        initSidebarCollapse();
        initBrandHomeNavigation();
        initTableChartToggles();
        activatePage(getStoredActivePage() || getCurrentActivePageId(), {persist: false});
        initSegmentsTableSorting();
        initSchemaSizesControls();
        initTableSizesControls();
        initViewsControls();
        initTempTablesControls();
        initDistributionControls();
        initActiveQueriesControls();
        initBlockingLocksControls();
        initIdleTransactionsControls();
        initMaintenanceStatsControls();
        initUsersControls();
        initGroupsControls();
        modalInstance = new bootstrap.Modal(document.getElementById('connectionModal'));

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
        donut.setAttribute('aria-label', `Использование слотов подключений: ${current} из ${maximum}, ${usageText}%`);
        summary.textContent = maximum > 0 ? `${current} из ${maximum} (${usageText}%)` : '—';
    }

    function renderDatabaseOverviewWarning(message) {
        const tbody = document.getElementById('databaseOverviewTableBody');
        const memoryTbody = document.getElementById('databaseOverviewMemoryTableBody');
        const connectionTbody = document.getElementById('databaseOverviewConnectionTableBody');
        const rolesTbody = document.getElementById('databaseOverviewRolesTableBody');
        const connectionSlotsTbody = document.getElementById('databaseOverviewConnectionSlotsTableBody');
        const basicSettingsTbody = document.getElementById('databaseOverviewBasicSettingsTableBody');
        const count = document.getElementById('databaseOverviewCount');
        const memoryCount = document.getElementById('databaseOverviewMemoryCount');
        const connectionCount = document.getElementById('databaseOverviewConnectionCount');
        const rolesCount = document.getElementById('databaseOverviewRolesCount');
        const connectionSlotsCount = document.getElementById('databaseOverviewConnectionSlotsCount');
        const basicSettingsCount = document.getElementById('databaseOverviewBasicSettingsCount');
        const version = document.getElementById('databaseOverviewVersion');
        if (count) count.textContent = 'Нет данных';
        if (memoryCount) memoryCount.textContent = 'Нет данных';
        if (connectionCount) connectionCount.textContent = 'Нет данных';
        if (rolesCount) rolesCount.textContent = 'Нет данных';
        if (connectionSlotsCount) connectionSlotsCount.textContent = 'Нет данных';
        if (basicSettingsCount) basicSettingsCount.textContent = 'Нет данных';
        updateConnectionSlotsChart([]);
        if (version) version.textContent = message;
        if (tbody) tbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
        if (memoryTbody) memoryTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
        if (connectionTbody) connectionTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
        if (rolesTbody) rolesTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
        if (connectionSlotsTbody) connectionSlotsTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
        if (basicSettingsTbody) basicSettingsTbody.innerHTML = `<tr><td colspan="2" class="text-muted">${message}</td></tr>`;
    }

    function renderDatabaseOverview(data) {
        const tbody = document.getElementById('databaseOverviewTableBody');
        const memoryTbody = document.getElementById('databaseOverviewMemoryTableBody');
        const connectionTbody = document.getElementById('databaseOverviewConnectionTableBody');
        const rolesTbody = document.getElementById('databaseOverviewRolesTableBody');
        const connectionSlotsTbody = document.getElementById('databaseOverviewConnectionSlotsTableBody');
        const basicSettingsTbody = document.getElementById('databaseOverviewBasicSettingsTableBody');
        const count = document.getElementById('databaseOverviewCount');
        const memoryCount = document.getElementById('databaseOverviewMemoryCount');
        const connectionCount = document.getElementById('databaseOverviewConnectionCount');
        const rolesCount = document.getElementById('databaseOverviewRolesCount');
        const connectionSlotsCount = document.getElementById('databaseOverviewConnectionSlotsCount');
        const basicSettingsCount = document.getElementById('databaseOverviewBasicSettingsCount');
        const version = document.getElementById('databaseOverviewVersion');
        const metrics = data.metrics || [];
        const memorySettings = data.memory_settings || [];
        const connectionInfo = data.connection_info || [];
        const roleCounts = data.role_counts || [];
        const connectionSlots = data.connection_slots || [];
        const basicSettings = data.basic_settings || [];
        if (count) count.textContent = `${metrics.length} метрик`;
        if (memoryCount) memoryCount.textContent = `${memorySettings.length} параметра`;
        if (connectionCount) connectionCount.textContent = `${connectionInfo.length} параметров`;
        if (rolesCount) rolesCount.textContent = `${roleCounts.length} показателя`;
        if (connectionSlotsCount) connectionSlotsCount.textContent = `${connectionSlots.length} показателя`;
        if (basicSettingsCount) basicSettingsCount.textContent = `${basicSettings.length} параметров`;
        if (version) version.textContent = data.database_version || '—';
        if (basicSettingsTbody) {
            if (!basicSettings.length) {
                basicSettingsTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных об основных данных БД</td></tr>';
            } else {
                basicSettingsTbody.innerHTML = basicSettings.map(item => `
                    <tr>
                        <td>${escapeHtml(item.label)}</td>
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
                memoryTbody.innerHTML = '<tr><td colspan="2" class="text-muted">Нет данных о параметрах памяти</td></tr>';
            } else {
                memoryTbody.innerHTML = memorySettings.map(item => `
                    <tr>
                        <td>${item.label}</td>
                        <td><strong>${item.value}</strong></td>
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
                        <td>${item.label}</td>
                        <td><strong>${item.count ?? 0}</strong></td>
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
                        <td>${item.label}</td>
                        <td><strong>${value}</strong></td>
                    </tr>
                `;
                }).join('');
            }
        }
    }

    function refreshDatabaseOverviewForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderDatabaseOverviewWarning('Выберите сохранённое подключение для загрузки размеров БД');
            return;
        }
        renderDatabaseOverviewWarning('Загрузка размеров БД...');
        connectionRequest(databaseOverviewApiUrl, {id: conn.id})
            .then(data => renderDatabaseOverview(data))
            .catch(error => renderDatabaseOverviewWarning(error.message || 'Не удалось получить размеры БД'));
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
            const icon = button.querySelector('i');
            const isActive = button.dataset.activeQuerySort === activeQueriesState.sort;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${activeQueriesState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function scheduleActiveQueriesRefresh() {
        if (activeQueriesState.timer) {
            clearInterval(activeQueriesState.timer);
            activeQueriesState.timer = null;
        }
        if (!activeQueriesState.refreshInterval) return;
        activeQueriesState.timer = setInterval(() => {
            if (document.getElementById('page-queries')?.classList.contains('active')) {
                refreshActiveQueriesForConnection(undefined, {silent: true});
            }
        }, activeQueriesState.refreshInterval * 1000);
    }

    function initActiveQueriesControls() {
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
        document.getElementById('activeQueriesRefreshBtn')?.addEventListener('click', function () {
            refreshActiveQueriesForConnection(undefined, {silent: false});
        });
        updateActiveQueriesSortIndicators();
    }

    function renderActiveQueriesWarning(message) {
        const tbody = document.getElementById('activeQueriesTableBody');
        const count = document.getElementById('activeQueriesCount');
        if (count) count.textContent = 'Нет данных';
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderActiveQueries(data) {
        const tbody = document.getElementById('activeQueriesTableBody');
        const count = document.getElementById('activeQueriesCount');
        const queries = sortActiveQueries(data.queries || []);
        updateActiveQueriesSortIndicators();
        if (count) count.textContent = `${queries.length} активных запросов`;
        if (!tbody) return;
        if (!queries.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-muted">Активные запросы не найдены</td></tr>';
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
            </tr>
        `).join('');
    }

    function refreshActiveQueriesForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId)), options = {}) {
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderActiveQueriesWarning('Выберите сохранённое подключение для загрузки активных запросов');
            return;
        }
        const requestId = ++activeQueriesRequestId;
        if (!options.silent) renderActiveQueriesWarning('Загрузка активных запросов...');
        connectionRequest(activeQueriesApiUrl, {id: conn.id})
            .then(data => {
                if (requestId !== activeQueriesRequestId) return;
                renderActiveQueries(data);
            })
            .catch(error => {
                if (requestId !== activeQueriesRequestId) return;
                renderActiveQueriesWarning(error.message || 'Не удалось получить активные запросы');
            });
    }

    function renderBlockingLocksWarning(message) {
        const tbody = document.getElementById('blockingLocksTableBody');
        const count = document.getElementById('blockingLocksCount');
        if (count) count.textContent = 'Нет данных';
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderBlockingLocks(data) {
        const tbody = document.getElementById('blockingLocksTableBody');
        const count = document.getElementById('blockingLocksCount');
        const locks = data.locks || [];
        if (count) count.textContent = `${locks.length} блокировок`;
        if (!tbody) return;
        if (!locks.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-muted">Блокировки не найдены</td></tr>';
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
            if (document.getElementById('page-locks')?.classList.contains('active')) {
                refreshBlockingLocksForConnection(undefined, {silent: true});
            }
        }, blockingLocksState.refreshInterval * 1000);
    }

    function initBlockingLocksControls() {
        document.getElementById('blockingLocksRefreshInterval')?.addEventListener('change', function () {
            blockingLocksState.refreshInterval = Number(this.value) || 0;
            scheduleBlockingLocksRefresh();
            refreshBlockingLocksForConnection(undefined, {silent: true});
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
        const requestId = ++blockingLocksRequestId;
        if (!options.silent) renderBlockingLocksWarning('Загрузка блокировок...');
        connectionRequest(blockingLocksApiUrl, {id: conn.id})
            .then(data => {
                if (requestId !== blockingLocksRequestId) return;
                renderBlockingLocks(data);
            })
            .catch(error => {
                if (requestId !== blockingLocksRequestId) return;
                renderBlockingLocksWarning(error.message || 'Не удалось получить блокировки');
            });
    }

    function renderIdleTransactionsWarning(message) {
        const tbody = document.getElementById('idleTransactionsTableBody');
        const count = document.getElementById('idleTransactionsCount');
        if (count) count.textContent = 'Нет данных';
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function renderIdleTransactions(data) {
        const tbody = document.getElementById('idleTransactionsTableBody');
        const count = document.getElementById('idleTransactionsCount');
        const transactions = data.transactions || [];
        if (count) count.textContent = `${transactions.length} транзакций`;
        if (!tbody) return;
        if (!transactions.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-muted">Транзакции не найдены</td></tr>';
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
            if (document.getElementById('page-transactions')?.classList.contains('active')) {
                refreshIdleTransactionsForConnection(undefined, {silent: true});
            }
        }, idleTransactionsState.refreshInterval * 1000);
    }

    function initIdleTransactionsControls() {
        document.getElementById('idleTransactionsRefreshInterval')?.addEventListener('change', function () {
            idleTransactionsState.refreshInterval = Number(this.value) || 0;
            scheduleIdleTransactionsRefresh();
            refreshIdleTransactionsForConnection(undefined, {silent: true});
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
        const requestId = ++idleTransactionsRequestId;
        if (!options.silent) renderIdleTransactionsWarning('Загрузка транзакций...');
        connectionRequest(idleTransactionsApiUrl, {id: conn.id})
            .then(data => {
                if (requestId !== idleTransactionsRequestId) return;
                renderIdleTransactions(data);
            })
            .catch(error => {
                if (requestId !== idleTransactionsRequestId) return;
                renderIdleTransactionsWarning(error.message || 'Не удалось получить транзакции');
            });
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
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderMemoryOverviewWarning('Выберите сохранённое подключение для загрузки памяти');
            return;
        }
        renderMemoryOverviewWarning('Загрузка памяти...');
        connectionRequest(memoryOverviewApiUrl, {id: conn.id})
            .then(data => renderMemoryOverview(data))
            .catch(error => renderMemoryOverviewWarning(error.message || 'Не удалось получить параметры памяти'));
    }

    function renderRolesListWarning(tbodyId, countId, colspan, message) {
        const tbody = document.getElementById(tbodyId);
        const count = document.getElementById(countId);
        if (count) count.textContent = 'Нет данных';
        if (tbody) tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-muted">${escapeHtml(message)}</td></tr>`;
    }

    function updateUsersSortIndicators() {
        document.querySelectorAll('[data-users-sort]').forEach(button => {
            const icon = button.querySelector('i');
            const isActive = button.dataset.usersSort === usersState.sort;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${usersState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function updateGroupsSortIndicators() {
        document.querySelectorAll('[data-groups-sort]').forEach(button => {
            const icon = button.querySelector('i');
            const isActive = button.dataset.groupsSort === groupsState.sort;
            button.classList.toggle('active', isActive);
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${groupsState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function updateUsersPaginationButtons() {
        const totalPages = Math.max(Math.ceil(usersState.totalCount / usersState.pageSize), 1);
        const prev = document.getElementById('usersPrevPageBtn');
        const next = document.getElementById('usersNextPageBtn');
        if (prev) prev.disabled = usersState.page <= 1;
        if (next) next.disabled = usersState.page >= totalPages;
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

    function renderUsersWarning(message) {
        const info = document.getElementById('usersPaginationInfo');
        usersState.totalCount = 0;
        updateUsersPrivilegeCharts([]);
        if (info) info.textContent = 'Страница 1 из 1';
        renderRolesListWarning('usersTableBody', 'usersCount', 8, message);
        updateUsersPaginationButtons();
    }

    function renderRolesList(data, tbodyId, countId, emptyMessage, includeMembersCount = false) {
        const tbody = document.getElementById(tbodyId);
        const count = document.getElementById(countId);
        const roles = data.roles || [];
        const colspan = includeMembersCount ? 9 : 8;
        if (count) count.textContent = `${roles.length} записей`;
        if (!tbody) return;
        if (!roles.length) {
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-muted">${escapeHtml(emptyMessage)}</td></tr>`;
            return;
        }
        tbody.innerHTML = roles.map(role => `
            <tr>
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
        `).join('');
    }

    function renderUsers(data) {
        const info = document.getElementById('usersPaginationInfo');
        const count = document.getElementById('usersCount');
        usersState.totalCount = Number(data.total_count) || 0;
        usersState.page = Number(data.page) || 1;
        usersState.pageSize = Number(data.page_size) || 100;
        updateUsersSortIndicators();
        updateUsersPrivilegeCharts(data.roles || [], data.summary || null);
        const totalPages = Math.max(Math.ceil(usersState.totalCount / usersState.pageSize), 1);
        renderRolesList(data, 'usersTableBody', null, 'Пользователи не найдены');
        if (count) count.textContent = `${data.roles?.length || 0} из ${usersState.totalCount} пользователей`;
        if (info) info.textContent = `Страница ${usersState.page} из ${totalPages}`;
        updateUsersPaginationButtons();
    }

    function refreshUsersForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const requestId = ++usersRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            renderUsersWarning('Выберите сохранённое подключение для загрузки пользователей');
            return;
        }
        renderUsersWarning('Загрузка пользователей...');
        connectionRequest(usersListApiUrl, {
            id: conn.id,
            page: usersState.page,
            search: usersState.search,
            sort: usersState.sort,
            direction: usersState.direction
        })
            .then(data => {
                if (requestId === usersRequestId) renderUsers(data);
            })
            .catch(error => {
                if (requestId === usersRequestId) renderUsersWarning(error.message || 'Не удалось получить список пользователей');
            });
    }

    function initUsersControls() {
        let searchTimer = null;
        document.getElementById('usersSearchInput')?.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                usersState.search = this.value.trim();
                usersState.page = 1;
                refreshUsersForConnection();
            }, 300);
        });
        document.querySelectorAll('[data-users-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.usersSort;
                if (usersState.sort === sort) {
                    usersState.direction = usersState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    usersState.sort = sort;
                    usersState.direction = ['connection_limit', 'valid_until'].includes(sort) ? 'desc' : 'asc';
                }
                usersState.page = 1;
                refreshUsersForConnection();
            });
        });
        document.getElementById('usersPrevPageBtn')?.addEventListener('click', function () {
            if (usersState.page > 1) {
                usersState.page -= 1;
                refreshUsersForConnection();
            }
        });
        document.getElementById('usersNextPageBtn')?.addEventListener('click', function () {
            const totalPages = Math.max(Math.ceil(usersState.totalCount / usersState.pageSize), 1);
            if (usersState.page < totalPages) {
                usersState.page += 1;
                refreshUsersForConnection();
            }
        });
        updateUsersSortIndicators();
        updateUsersPaginationButtons();
    }

    function refreshGroupsForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const requestId = ++groupsRequestId;
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            updateGroupsPrivilegeCharts([]);
            renderRolesListWarning('groupsTableBody', 'groupsCount', 9, 'Выберите сохранённое подключение для загрузки групп');
            return;
        }
        updateGroupsPrivilegeCharts([]);
        renderRolesListWarning('groupsTableBody', 'groupsCount', 9, 'Загрузка групп...');
        connectionRequest(groupsListApiUrl, {
            id: conn.id,
            search: groupsState.search,
            sort: groupsState.sort,
            direction: groupsState.direction
        })
            .then(data => {
                if (requestId !== groupsRequestId) return;
                updateGroupsSortIndicators();
                updateGroupsPrivilegeCharts(data.roles || [], data.summary || null);
                renderRolesList(data, 'groupsTableBody', 'groupsCount', 'Группы не найдены', true);
            })
            .catch(error => {
                if (requestId !== groupsRequestId) return;
                updateGroupsPrivilegeCharts([]);
                renderRolesListWarning('groupsTableBody', 'groupsCount', 9, error.message || 'Не удалось получить список групп');
            });
    }

    function initGroupsControls() {
        let searchTimer = null;
        document.getElementById('groupsSearchInput')?.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                groupsState.search = this.value.trim();
                refreshGroupsForConnection();
            }, 300);
        });
        document.querySelectorAll('[data-groups-sort]').forEach(button => {
            button.addEventListener('click', function () {
                const sort = this.dataset.groupsSort;
                if (groupsState.sort === sort) {
                    groupsState.direction = groupsState.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    groupsState.sort = sort;
                    groupsState.direction = ['connection_limit', 'valid_until', 'member_count'].includes(sort) ? 'desc' : 'asc';
                }
                refreshGroupsForConnection();
            });
        });
        updateGroupsSortIndicators();
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
        const deadPercentBars = document.getElementById('maintenanceDeadPercentBars');
        const deadRowsBars = document.getElementById('maintenanceDeadRowsBars');
        const heatmap = document.getElementById('maintenanceStatusHeatmap');
        const donut = document.getElementById('maintenanceRowsDonut');
        const donutSummary = document.getElementById('maintenanceRowsDonutSummary');
        const donutTable = document.getElementById('maintenanceRowsDonutTable');
        if (deadPercentBars) deadPercentBars.textContent = 'Нет данных';
        if (deadRowsBars) deadRowsBars.textContent = 'Нет данных';
        if (heatmap) heatmap.textContent = 'Нет данных';
        if (donut) donut.style.setProperty('--maintenance-live-dead', '#e8eaee 0 100%');
        if (donutSummary) donutSummary.textContent = '—';
        if (donutTable) donutTable.textContent = 'Выберите таблицу';
    }

    function renderMaintenanceBarChart(containerId, tables, valueGetter, valueFormatter, maxValue = null) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const topTables = [...tables]
            .sort((a, b) => valueGetter(b) - valueGetter(a))
            .slice(0, 10);
        const max = maxValue ?? Math.max(...topTables.map(valueGetter), 0);
        if (!topTables.length || max <= 0) {
            container.textContent = 'Нет данных';
            return;
        }
        container.innerHTML = topTables.map(table => {
            const value = valueGetter(table);
            const percent = Math.max((value * 100) / max, 2);
            const statusClass = getMaintenanceStatusClass(Number(table.dead_percent) || 0);
            const tableName = getMaintenanceTableKey(table);
            return `
                <div class="maintenance-bar-row" title="${escapeHtml(tableName)}">
                    <span class="maintenance-bar-name">${escapeHtml(tableName)}</span>
                    <span class="maintenance-bar-track"><span class="maintenance-bar-fill ${statusClass}" style="width:${percent}%;"></span></span>
                    <span class="maintenance-bar-value">${escapeHtml(valueFormatter(value))}</span>
                </div>
            `;
        }).join('');
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
        renderMaintenanceBarChart('maintenanceDeadPercentBars', tables, table => Number(table.dead_percent) || 0, value => `${value}%`, 100);
        renderMaintenanceBarChart('maintenanceDeadRowsBars', tables, table => Number(table.dead_rows) || 0, value => formatRowCount(value));
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
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-muted">${escapeHtml(message)}</td></tr>`;
        updateMaintenancePaginationControls();
    }

    function updateMaintenancePaginationControls() {
        const totalPages = Math.max(Math.ceil(maintenanceStatsState.totalCount / maintenanceStatsState.pageSize), 1);
        const prev = document.getElementById('maintenancePrevPageBtn');
        const next = document.getElementById('maintenanceNextPageBtn');
        if (prev) prev.disabled = maintenanceStatsState.page <= 1;
        if (next) next.disabled = maintenanceStatsState.page >= totalPages;
    }

    function updateMaintenanceSortIndicators() {
        document.querySelectorAll('[data-maintenance-sort]').forEach(button => {
            const icon = button.querySelector('i');
            const isActive = button.dataset.maintenanceSort === maintenanceStatsState.sort;
            if (!icon) return;
            icon.className = isActive
                ? `fas fa-sort-${maintenanceStatsState.direction === 'asc' ? 'up' : 'down'}`
                : 'fas fa-sort';
        });
    }

    function renderMaintenanceStats(data) {
        const tbody = document.getElementById('maintenanceStatsTableBody');
        const count = document.getElementById('maintenanceStatsCount');
        const info = document.getElementById('maintenancePageInfo');
        const tables = data.tables || [];
        maintenanceStatsState.totalCount = Number(data.total_count) || 0;
        maintenanceStatsState.page = Number(data.page) || 1;
        maintenanceStatsState.pageSize = Number(data.page_size) || 100;
        const totalPages = Math.max(Math.ceil(maintenanceStatsState.totalCount / maintenanceStatsState.pageSize), 1);
        if (count) count.textContent = `${tables.length} из ${maintenanceStatsState.totalCount} таблиц`;
        if (info) info.textContent = `Страница ${maintenanceStatsState.page} из ${totalPages}`;
        updateMaintenanceSortIndicators();
        updateMaintenancePaginationControls();
        updateMaintenanceVisuals(tables);
        if (!tbody) return;
        if (!tables.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Статистика обслуживания не найдена</td></tr>';
            return;
        }
        tbody.innerHTML = tables.map(table => {
            const deadPercent = Number(table.dead_percent) || 0;
            const deadClass = deadPercent >= 10 ? 'text-danger' : (deadPercent >= 1 ? 'text-warning' : 'text-success');
            const tableKey = getMaintenanceTableKey(table);
            const activeClass = tableKey === maintenanceStatsState.selectedTableKey ? ' active' : '';
            return `
                <tr class="maintenance-row-selectable${activeClass}" data-maintenance-table-key="${escapeHtml(tableKey)}">
                    <td>${escapeHtml(table.schema_name)}</td>
                    <td><code>${escapeHtml(table.table_name)}</code></td>
                    <td>${formatRowCount(table.live_rows)}</td>
                    <td>${formatRowCount(table.dead_rows)}</td>
                    <td><span class="${deadClass}">${deadPercent}%</span></td>
                    <td>${escapeHtml(table.last_vacuum)}</td>
                    <td>${escapeHtml(table.last_analyze)}</td>
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

    function renderSchemaSizesWarning(message) {
        const tbody = document.getElementById('schemaSizesTableBody');
        const count = document.getElementById('schemaSizesCount');
        const info = document.getElementById('schemaPaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        updateSchemaDistributionChart([]);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-muted">${message}</td></tr>`;
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
        updateSchemaDistributionChart(data.schema_distribution || data.schemas || []);
        const totalPages = Math.max(Math.ceil(schemaSizesState.totalCount / schemaSizesState.pageSize), 1);
        if (count) count.textContent = `${data.schemas?.length || 0} из ${schemaSizesState.totalCount} схем`;
        if (info) info.textContent = `Страница ${schemaSizesState.page} из ${totalPages}`;
        if (!data.schemas?.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Схемы не найдены</td></tr>';
            updateSchemaPaginationButtons();
            return;
        }
        tbody.innerHTML = data.schemas.map(schema => `
            <tr>
                <td><strong>${schema.schema_name || '-'}</strong></td>
                <td>${schema.schema_owner || '-'}</td>
                <td>${schema.table_count ?? 0}</td>
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

    function refreshSchemaSizesForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
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
    function renderTableSizesWarning(message) {
        const tbody = document.getElementById('tableSizesTableBody');
        const count = document.getElementById('tableSizesCount');
        const info = document.getElementById('tablePaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        updateTableDistributionChart([]);
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
        updateTableDistributionChart(data.table_distribution || data.tables || []);
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

    function refreshTableSizesForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
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

    function renderViewsWarning(message) {
        const tbody = document.getElementById('viewsTableBody');
        const count = document.getElementById('viewsCount');
        const info = document.getElementById('viewPaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        updateViewsSummaryChart(null, []);
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
        updateViewsSummaryChart(data.summary || null, data.views || []);
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

    function refreshViewsForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
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
            view_type: viewsState.viewType,
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
        document.getElementById('viewTypeFilter')?.addEventListener('change', function () {
            viewsState.viewType = this.value;
            viewsState.page = 1;
            refreshViewsForConnection();
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

    function distributionTableOptionLabel(table) {
        return `${table.schema_name}.${table.table_name}`;
    }

    function getFilteredDistributionTables(query = '') {
        const normalizedQuery = String(query || '').trim().toLowerCase();
        if (!normalizedQuery) return distributionTables;
        return distributionTables.filter(table => distributionTableOptionLabel(table).toLowerCase().includes(normalizedQuery));
    }

    function setDistributionTableDropdownVisible(isVisible) {
        const dropdown = document.getElementById('distributionTableDropdown');
        const toggle = document.getElementById('distributionTableListToggle');
        if (dropdown) dropdown.classList.toggle('d-none', !isVisible);
        if (toggle) toggle.setAttribute('aria-expanded', String(isVisible));
    }

    function renderDistributionTableDropdown(tables = distributionTables) {
        const dropdown = document.getElementById('distributionTableDropdown');
        if (!dropdown) return;
        if (!tables.length) {
            dropdown.innerHTML = '<div class="distribution-table-dropdown-empty">Таблицы не найдены</div>';
            return;
        }
        dropdown.innerHTML = tables.map(table => {
            const label = distributionTableOptionLabel(table);
            return `
                <button class="distribution-table-dropdown-item" type="button" role="option" data-distribution-table="${escapeHtml(label)}">
                    <span>${escapeHtml(label)}</span>
                    <small>${escapeHtml(table.object_type || 'Таблица')}</small>
                </button>
            `;
        }).join('');
    }

    function showDistributionTableDropdown() {
        renderDistributionTableDropdown(distributionTables);
        setDistributionTableDropdownVisible(true);
    }

    function hideDistributionTableDropdown() {
        setDistributionTableDropdownVisible(false);
    }

    function refreshDistributionForSelectedTable() {
        const select = document.getElementById('distributionTableSelect');
        const selectedValue = (select?.value || '').trim();
        const selectedTable = distributionTables.find(table => distributionTableOptionLabel(table) === selectedValue);
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
        const options = document.getElementById('distributionTableOptions');
        const count = document.getElementById('distributionTableCount');
        if (count) count.textContent = `${tables.length} таблиц`;
        if (!select || !options) return;
        if (!tables.length) {
            select.value = '';
            select.placeholder = 'Таблицы не найдены';
            options.innerHTML = '';
            renderDistributionTableDropdown([]);
            hideDistributionTableDropdown();
            renderDistributionWarning('Таблицы не найдены');
            return;
        }
        options.innerHTML = tables.map(table => {
            const label = distributionTableOptionLabel(table);
            return `<option value="${escapeHtml(label)}" label="${escapeHtml(table.object_type || 'Таблица')}"></option>`;
        }).join('');
        renderDistributionTableDropdown(tables);
        select.placeholder = 'Начните вводить схему или название таблицы';
        if (!tables.some(table => distributionTableOptionLabel(table) === select.value)) {
            select.value = distributionTableOptionLabel(tables[0]);
        }
        refreshDistributionForSelectedTable();
    }

    function refreshDistributionTablesForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const select = document.getElementById('distributionTableSelect');
        const options = document.getElementById('distributionTableOptions');
        if (!conn || !/^\d+$/.test(String(conn.id))) {
            distributionTables = [];
            if (select) {
                select.value = '';
                select.placeholder = 'Выберите сохранённое подключение для загрузки таблиц';
            }
            if (options) options.innerHTML = '';
            renderDistributionTableDropdown([]);
            hideDistributionTableDropdown();
            renderDistributionWarning('Выберите сохранённое подключение для загрузки списка таблиц');
            return;
        }
        if (select) {
            select.value = '';
            select.placeholder = 'Загрузка таблиц...';
        }
        if (options) options.innerHTML = '';
        renderDistributionTableDropdown([]);
        hideDistributionTableDropdown();
        connectionRequest(distributionTablesApiUrl, {id: conn.id})
            .then(data => {
                distributionTables = data.tables || [];
                renderDistributionTableOptions(distributionTables);
            })
            .catch(error => {
                distributionTables = [];
                if (select) {
                    select.value = '';
                    select.placeholder = 'Не удалось загрузить таблицы';
                }
                if (options) options.innerHTML = '';
                renderDistributionTableDropdown([]);
                hideDistributionTableDropdown();
                renderDistributionWarning(error.message || 'Не удалось загрузить список таблиц');
            });
    }

    function initDistributionControls() {
        const select = document.getElementById('distributionTableSelect');
        const toggle = document.getElementById('distributionTableListToggle');
        const dropdown = document.getElementById('distributionTableDropdown');

        select?.addEventListener('change', refreshDistributionForSelectedTable);
        select?.addEventListener('input', function () {
            if (dropdown && !dropdown.classList.contains('d-none')) {
                renderDistributionTableDropdown(getFilteredDistributionTables(this.value));
            }
        });
        select?.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                refreshDistributionForSelectedTable();
                hideDistributionTableDropdown();
            }
            if (event.key === 'Escape') {
                hideDistributionTableDropdown();
            }
        });
        toggle?.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            const isOpen = dropdown && !dropdown.classList.contains('d-none');
            if (isOpen) {
                hideDistributionTableDropdown();
            } else {
                showDistributionTableDropdown();
                select?.focus();
            }
        });
        dropdown?.addEventListener('click', function (event) {
            const item = event.target.closest('[data-distribution-table]');
            if (!item || !select) return;
            select.value = item.dataset.distributionTable || '';
            hideDistributionTableDropdown();
            refreshDistributionForSelectedTable();
        });
        document.addEventListener('click', function (event) {
            if (!event.target.closest('.search-box-wide')) {
                hideDistributionTableDropdown();
            }
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
    function renderTempTablesWarning(message) {
        const tbody = document.getElementById('tempTablesTableBody');
        const count = document.getElementById('tempTablesCount');
        const info = document.getElementById('tempTablePaginationInfo');
        if (count) count.textContent = 'Нет данных';
        if (info) info.textContent = 'Страница 1 из 1';
        updateTempTableDistributionChart([]);
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
        updateTempTableDistributionChart(data.temp_table_distribution || data.temp_tables || []);
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

    function refreshTempTablesForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
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

    function refreshSegmentsForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
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


    function updateConnectionTooltip(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        const database = document.getElementById('connectionTooltipDatabase');
        const host = document.getElementById('connectionTooltipHost');
        const port = document.getElementById('connectionTooltipPort');
        const owner = document.getElementById('connectionTooltipOwner');
        const select = document.getElementById('connectionSelect');
        const databaseValue = conn?.database || '—';
        const hostValue = conn?.host || '—';
        const portValue = conn?.port || '—';
        const ownerValue = conn?.created_by || '—';

        if (database) database.textContent = databaseValue;
        if (host) host.textContent = hostValue;
        if (port) port.textContent = portValue;
        if (owner) owner.textContent = ownerValue;
        if (select) {
            select.title = conn
                ? `База данных: ${databaseValue}
Хост: ${hostValue}
Порт: ${portValue}
Владелец подключения: ${ownerValue}`
                : 'Информация о подключении недоступна';
        }
    }

    function populateConnectionSelect() {
        const select = document.getElementById('connectionSelect');
        select.innerHTML = '';
        if (!connections.length) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Нет доступных подключений';
            select.appendChild(option);
            select.value = '';
            updateConnectionTooltip(null);
            updateSidebarForConnection(null);
            persistActiveConnectionId(null);
            return;
        }
        connections.forEach(conn => {
            const option = document.createElement('option');
            option.value = conn.id;
            option.textContent = conn.name;
            select.appendChild(option);
        });
        if (activeConnectionId) {
            select.value = activeConnectionId;
            persistActiveConnectionId(activeConnectionId);
        }
        updateConnectionTooltip();
        updateSidebarForConnection();
    }

    function isKnownPage(pageId) {
        return Boolean(
            pageId &&
            pageTitles[pageId] &&
            document.getElementById('page-' + pageId) &&
            isPageAvailableForConnection(pageId) &&
            (
                pageId === 'home'
                || Array.from(document.querySelectorAll('.nav-item')).some(item => item.dataset.page === pageId && !item.classList.contains('d-none'))
            )
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
        if (pageId === 'temp-tables') {
            refreshTempTablesForConnection(conn);
        }
        if (pageId === 'distribution') {
            refreshDistributionTablesForConnection(conn);
        }
        if (pageId === 'queries') {
            refreshActiveQueriesForConnection(conn);
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
    }

    function refreshActivePageForConnection(conn = connections.find(c => String(c.id) === String(activeConnectionId))) {
        refreshPageData(getCurrentActivePageId(), conn);
    }

    function activatePage(pageId, {persist = true, refresh = true} = {}) {
        updateSidebarForConnection();
        const nextPageId = isKnownPage(pageId) ? pageId : getDefaultPageForConnection();

        document.querySelectorAll('.nav-item').forEach(item => {
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
        if (conn) {
            updateSidebarForConnection(conn);
            activatePage(getDefaultPageForConnection(conn));
            if (!isPostgreSQLConnection(conn)) {
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
        document.getElementById('connName').value = 'New Connection';
        document.getElementById('connHost').value = 'localhost';
        document.getElementById('connPort').value = '5432';
        document.getElementById('connDatabase').value = 'postgres';
        document.getElementById('connUser').value = 'postgres';
        document.getElementById('connDbType').value = 'PostgreSQL';
        document.getElementById('connPassword').value = '';
    }

    function editConnection() {
        if (!canManageConnections()) {
            showToast('⛔ Редактировать подключения может только Администратор');
            return;
        }
        const conn = connections.find(c => String(c.id) === String(activeConnectionId));
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

        if (!confirm(`Удалить подключение "${conn.name}"?`)) {
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
                    populateConnectionSelect();

                document.getElementById('connectionSelect').value = savedConnection.id;
                activeConnectionId = savedConnection.id;
                persistActiveConnectionId(activeConnectionId);
                updateSidebarForConnection(savedConnection);
                activatePage(getDefaultPageForConnection(savedConnection));
                if (!isPostgreSQLConnection(savedConnection)) {
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

    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            Object.values(charts).forEach(chart => {
                if (chart && chart.resize) chart.resize();
            });
        }
    });
