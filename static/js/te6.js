// ============================
    // STATE
    // ============================
    let connections = [];
    let activeConnectionId = 'prod-greenplum';
    let charts = {};
    let modalInstance = null;

    const defaultConnections = [
        {id: 'prod-greenplum', name: 'Production GP', host: 'gp-prod.example.com', port: 5432, database: 'postgres', user: 'gpadmin', ssl: true, status: 'online'},
        {id: 'dev-greenplum', name: 'Dev Greenplum', host: 'gp-dev.example.com', port: 5432, database: 'postgres', user: 'gpadmin', ssl: true, status: 'online'},
        {id: 'test-postgres', name: 'Test PostgreSQL', host: 'localhost', port: 5432, database: 'postgres', user: 'postgres', ssl: false, status: 'online'},
        {id: 'analytics', name: 'Analytics Cluster', host: 'analytics.example.com', port: 5432, database: 'analytics', user: 'analytics_user', ssl: true, status: 'online'}
    ];

    // ============================
    // INIT
    // ============================
    document.addEventListener('DOMContentLoaded', function () {
        loadConnections();
        updateClock();
        setInterval(updateClock, 1000);
        initCharts();
        initNavigation();
        updateConnectionUI();
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
    function loadConnections() {
        const saved = localStorage.getItem('gp_connections');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                connections = parsed;
                const defaultIds = defaultConnections.map(c => c.id);
                const savedIds = connections.map(c => c.id);
                defaultConnections.forEach(dc => {
                    if (!savedIds.includes(dc.id)) {
                        connections.push(dc);
                    }
                });
            } catch (e) {
                connections = [...defaultConnections];
            }
        } else {
            connections = [...defaultConnections];
        }
        saveConnections();
        populateConnectionSelect();
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
            const icon = conn.status === 'online' ? '🟢' : conn.status === 'connecting' ? '🟡' : '🔴';
            option.textContent = `${icon} ${conn.name}`;
            select.appendChild(option);
        });
        if (activeConnectionId) {
            select.value = activeConnectionId;
        }
    }

    function onConnectionChange(connId) {
        activeConnectionId = connId;
        const conn = connections.find(c => c.id === connId);
        if (conn) {
            updateConnectionUI();
            showToast(`🔌 Подключено к ${conn.name}`);
            refreshAll();
        }
    }

    function updateConnectionUI() {
        const conn = connections.find(c => c.id === activeConnectionId);
        if (!conn) return;

        const indicator = document.getElementById('connStatusIndicator');
        indicator.className = 'conn-status ' + (conn.status === 'online' ? 'online' : conn.status === 'connecting' ? 'connecting' : 'offline');

        const info = document.getElementById('connectionInfo');
        info.textContent = `${conn.host}:${conn.port}`;
    }

    function openConnectionModal() {
        modalInstance.show();
        document.getElementById('connName').value = 'New Connection';
        document.getElementById('connHost').value = 'localhost';
        document.getElementById('connPort').value = '5432';
        document.getElementById('connDatabase').value = 'postgres';
        document.getElementById('connUser').value = 'postgres';
        document.getElementById('connPassword').value = '';
        document.getElementById('connSSL').checked = true;
    }

    function saveConnection() {
        const name = document.getElementById('connName').value.trim();
        const host = document.getElementById('connHost').value.trim();
        const port = parseInt(document.getElementById('connPort').value);
        const database = document.getElementById('connDatabase').value.trim();
        const user = document.getElementById('connUser').value.trim();
        const password = document.getElementById('connPassword').value;
        const ssl = document.getElementById('connSSL').checked;

        if (!name || !host || !port || !database || !user) {
            showToast('⚠️ Заполните все обязательные поля');
            return;
        }

        const newConn = {
            id: 'conn_' + Date.now(),
            name: name,
            host: host,
            port: port,
            database: database,
            user: user,
            ssl: ssl,
            status: 'online'
        };

        connections.push(newConn);
        saveConnections();
        populateConnectionSelect();

        document.getElementById('connectionSelect').value = newConn.id;
        activeConnectionId = newConn.id;
        updateConnectionUI();
        modalInstance.hide();
        showToast(`✅ Подключение "${name}" создано`);
        refreshAll();
    }

    function testConnection() {
        const conn = connections.find(c => c.id === activeConnectionId);
        if (!conn) {
            showToast('⚠️ Подключение не выбрано');
            return;
        }

        showToast(`🔍 Проверка ${conn.name}...`);
        setTimeout(() => {
            conn.status = 'online';
            updateConnectionUI();
            showToast(`✅ Подключение к ${conn.name} успешно`);
        }, 800);
    }

    function disconnect() {
        const conn = connections.find(c => c.id === activeConnectionId);
        if (!conn) return;
        conn.status = 'offline';
        updateConnectionUI();
        showToast(`🔌 Отключено от ${conn.name}`);
    }

    // ============================
    // CLOCK
    // ============================
    function updateClock() {
        const now = new Date();
        document.getElementById('currentTime').textContent = now.toLocaleString('ru-RU', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }

    // ============================
    // NAVIGATION
    // ============================
    function initNavigation() {
        const items = document.querySelectorAll('.nav-item');
        const pages = document.querySelectorAll('.page');
        const titles = {
            'dashboard': 'Дашборд <small>Общая сводка состояния кластера</small>',
            'segments': 'Сегменты <small>Состояние и конфигурация</small>',
            'cluster-health': 'Здоровье кластера <small>Метрики доступности</small>',
            'databases': 'Базы данных <small>Размеры и статистика</small>',
            'tables': 'Таблицы <small>Список и размеры таблиц</small>',
            'distribution': 'Распределение <small>Перекос данных</small>',
            'temp-tables': 'Временные таблицы <small>Активные временные таблицы</small>',
            'queries': 'Активные запросы <small>Долгие запросы</small>',
            'locks': 'Блокировки <small>Кто кого блокирует</small>',
            'transactions': 'Транзакции <small>Commit / Rollback</small>',
            'memory': 'Память <small>Параметры памяти</small>',
            'bloat': 'Раздувание <small>Bloat анализ</small>',
            'maintenance': 'Обслуживание <small>VACUUM / ANALYZE</small>'
        };

        items.forEach(item => {
            item.addEventListener('click', function (e) {
                e.preventDefault();
                const pageId = this.dataset.page;

                items.forEach(i => i.classList.remove('active'));
                this.classList.add('active');

                pages.forEach(p => p.classList.remove('active'));
                const target = document.getElementById('page-' + pageId);
                if (target) target.classList.add('active');

                document.getElementById('pageTitle').innerHTML = titles[pageId] || pageId;

                setTimeout(() => {
                    Object.values(charts).forEach(chart => {
                        if (chart && chart.resize) chart.resize();
                    });
                }, 100);

                if (window.innerWidth <= 992) {
                    document.getElementById('sidebar').classList.remove('open');
                }
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
        const btn = document.querySelector('.refresh-btn');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        btn.disabled = true;

        setTimeout(() => {
            btn.innerHTML = '<i class="fas fa-sync-alt"></i>';
            btn.disabled = false;
            showToast('✅ Данные обновлены');
        }, 1200);
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

        // ---- 1. Dashboard Activity ----
        const ctx1 = document.getElementById('dashboardActivityChart').getContext('2d');
        charts.dashboardActivity = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
                datasets: [{
                    label: 'Запросов',
                    data: [12, 8, 5, 3, 15, 42, 68, 85, 73, 54, 28, 18],
                    backgroundColor: 'rgba(79, 140, 255, 0.3)',
                    borderColor: colors.blue,
                    borderWidth: 1,
                    borderRadius: 4
                }, {
                    label: 'Долгие (>1мин)',
                    data: [2, 1, 0, 0, 3, 5, 8, 12, 9, 6, 4, 2],
                    backgroundColor: 'rgba(245, 158, 11, 0.3)',
                    borderColor: colors.yellow,
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: chartOptions
        });

        // ---- 2. Dashboard Transactions ----
        const ctx2 = document.getElementById('dashboardTxChart').getContext('2d');
        charts.dashboardTx = new Chart(ctx2, {
            type: 'doughnut',
            data: {
                labels: ['Коммиты', 'Роллбеки'],
                datasets: [{
                    data: [94.2, 5.8],
                    backgroundColor: [colors.green, colors.red],
                    borderColor: ['#ffffff', '#ffffff'],
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {color: '#4a5568', boxWidth: 12, padding: 15, font: {size: 12, family: 'Inter'}}
                    }
                }
            }
        });

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

        // ---- 4. Health Gauge ----
        const ctx4 = document.getElementById('healthGaugeChart').getContext('2d');
        charts.healthGauge = new Chart(ctx4, {
            type: 'doughnut',
            data: {
                labels: ['Здорово', 'Проблемы'],
                datasets: [{
                    data: [98.7, 1.3],
                    backgroundColor: [colors.green, 'rgba(239,68,68,0.15)'],
                    borderColor: ['#ffffff', '#ffffff'],
                    borderWidth: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '80%',
                plugins: {legend: {display: false}}
            }
        });

        // ---- 5. Health Metrics ----
        const ctx5 = document.getElementById('healthMetricsChart').getContext('2d');
        charts.healthMetrics = new Chart(ctx5, {
            type: 'bar',
            data: {
                labels: ['Подняты', 'Синхронизированы', 'Primary', 'Mirror'],
                datasets: [{
                    label: 'Сегменты',
                    data: [12, 12, 6, 6],
                    backgroundColor: [colors.green, colors.green, colors.blue, colors.teal],
                    borderRadius: 4
                }]
            },
            options: {
                ...chartOptions,
                plugins: {legend: {display: false}},
                scales: {
                    x: {ticks: {color: '#8a9bb0', font: {size: 11, family: 'Inter'}}, grid: {color: 'rgba(0,0,0,0.04)'}},
                    y: {ticks: {stepSize: 2, color: '#8a9bb0', font: {size: 9, family: 'Inter'}}, grid: {color: 'rgba(0,0,0,0.04)'}}
                }
            }
        });

        // ---- 6. Database Sizes ----
        const ctx6 = document.getElementById('dbSizeChart').getContext('2d');
        charts.dbSize = new Chart(ctx6, {
            type: 'bar',
            data: {
                labels: ['dd04_finance', 'dwh_cube', 'dc00_sys', 'postgres', 'template1', 'template0', 'gpperfmon', 'gpadmin'],
                datasets: [{
                    label: 'Размер (GB)',
                    data: [745.2, 412.8, 156.3, 42.1, 28.5, 28.5, 12.7, 8.9],
                    backgroundColor: [colors.green, colors.blue, colors.purple, colors.orange, colors.yellow, colors.yellow, colors.teal, colors.pink],
                    borderRadius: 4
                }]
            },
            options: {
                ...chartOptions,
                plugins: {legend: {display: false}}
            }
        });

        // ---- 7. Skew ----
        const ctx7 = document.getElementById('skewChart').getContext('2d');
        charts.skew = new Chart(ctx7, {
            type: 'bar',
            data: {
                labels: ['dd04443_bal', 'fact_sales', 'dd04443_tx', 'dc00006_audit', 'fact_orders', 'dim_customer'],
                datasets: [{
                    label: 'Коэффициент перекоса',
                    data: [1.89, 1.45, 1.23, 1.18, 1.12, 1.05],
                    backgroundColor: [colors.red, colors.yellow, colors.yellow, colors.green, colors.green, colors.green],
                    borderRadius: 4
                }]
            },
            options: {
                ...chartOptions,
                plugins: {legend: {display: false}}
            }
        });

        // ---- 8. Segment Distribution ----
        const ctx8 = document.getElementById('segmentDistributionChart').getContext('2d');
        charts.segmentDist = new Chart(ctx8, {
            type: 'bar',
            data: {
                labels: ['sg0', 'sg1', 'sg2', 'sg3', 'sg4', 'sg5'],
                datasets: [{
                    label: 'Строк (млн)',
                    data: [185.7, 178.2, 192.4, 98.2, 165.8, 172.9],
                    backgroundColor: ['#4f8cff', '#4f8cff', '#4f8cff', '#ef4444', '#4f8cff', '#4f8cff'],
                    borderRadius: 4
                }]
            },
            options: {
                ...chartOptions,
                plugins: {legend: {display: false}}
            }
        });

        // ---- 9. Temp Users ----
        const ctx9 = document.getElementById('tempUsersChart').getContext('2d');
        charts.tempUsers = new Chart(ctx9, {
            type: 'doughnut',
            data: {
                labels: ['etl_loader', 'report_user', 'dwhnbrb_cube', 'other'],
                datasets: [{
                    data: [35.2, 28.6, 18.4, 17.8],
                    backgroundColor: [colors.blue, colors.green, colors.purple, '#d1d5db'],
                    borderColor: ['#ffffff', '#ffffff', '#ffffff', '#ffffff'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {color: '#4a5568', boxWidth: 12, padding: 12, font: {size: 11, family: 'Inter'}}
                    }
                }
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
