/**
 * Marq Lab - Modern Minimalist Frontend Engine (v3.0)
 * 4 Dedicated Menus (Mineração, Central de Leads, Agenda, Métricas & Funil),
 * Full company names without truncation, Agenda meeting removal, and Horizontal Sales Funnel Chart.
 */

// Application State
let appState = {
    theme: localStorage.getItem('marq_theme') || 'dark',
    companyWidthMode: localStorage.getItem('marq_company_width') || 'normal',
    currentView: 'mineracao',
    isRunning: false,
    currentLeads: [],
    statusChart: null,
    funnelChart: null,
    eventSource: null,
    activeLeadData: null,
    schedulingLeadId: null,
};

// DOM Ready initialization
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initCompanyWidth();
    setupEventListeners();
    loadDashboardData();
    connectSSE();
});

// ----------------------------------------------------
// COLUMN WIDTH CONTROLLER (NOME DA EMPRESA)
// ----------------------------------------------------
function initCompanyWidth() {
    updateCompanyWidthButtons();
}

function getCompanyColWidthStyle() {
    switch (appState.companyWidthMode) {
        case 'wide':
            return 'min-width: 460px; max-width: 580px;';
        case 'extra':
            return 'min-width: 600px; max-width: 750px;';
        case 'full':
            return 'min-width: 480px; width: 100%;';
        case 'normal':
        default:
            return 'min-width: 320px; max-width: 440px;';
    }
}

function updateCompanyWidthButtons() {
    const modes = ['normal', 'wide', 'extra', 'full'];
    modes.forEach(m => {
        const btn = document.getElementById(`btnWidth${m.charAt(0).toUpperCase() + m.slice(1)}`);
        if (btn) {
            if (m === appState.companyWidthMode) {
                btn.className = 'px-2.5 py-1 rounded-lg text-[11px] font-bold border border-brand-500 bg-brand-500/10 text-brand-600 dark:text-brand-400 shadow-sm';
            } else {
                btn.className = 'px-2.5 py-1 rounded-lg text-[11px] font-semibold border border-slate-200 dark:border-darkborder bg-white dark:bg-darkcard text-slate-700 dark:text-slate-300 hover:border-brand-500 transition shadow-sm';
            }
        }
    });

    const th = document.getElementById('thCompanyCol');
    if (th) {
        let minW = '320px';
        if (appState.companyWidthMode === 'wide') minW = '460px';
        if (appState.companyWidthMode === 'extra') minW = '600px';
        if (appState.companyWidthMode === 'full') minW = '480px';
        th.style.minWidth = minW;
    }

    document.querySelectorAll('.company-col-cell').forEach(cell => {
        cell.setAttribute('style', getCompanyColWidthStyle());
    });
}

function setCompanyWidth(mode) {
    appState.companyWidthMode = mode;
    localStorage.setItem('marq_company_width', mode);
    updateCompanyWidthButtons();
}

function cycleCompanyWidth() {
    const sequence = ['normal', 'wide', 'extra', 'full'];
    const currIdx = sequence.indexOf(appState.companyWidthMode);
    const nextIdx = (currIdx + 1) % sequence.length;
    setCompanyWidth(sequence[nextIdx]);
}


// ----------------------------------------------------
// THEME SWITCHER
// ----------------------------------------------------
function initTheme() {
    const html = document.documentElement;
    const themeIcon = document.getElementById('themeIcon');
    if (appState.theme === 'dark') {
        html.classList.add('dark');
        if (themeIcon) themeIcon.className = 'ph-bold ph-sun text-lg';
    } else {
        html.classList.remove('dark');
        if (themeIcon) themeIcon.className = 'ph-bold ph-moon text-lg';
    }
}

function toggleTheme() {
    appState.theme = appState.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('marq_theme', appState.theme);
    initTheme();
    updateChartsTheme();
}

// ----------------------------------------------------
// 4 DEDICATED MENUS / VIEW SWITCHER
// ----------------------------------------------------
function switchView(viewName) {
    appState.currentView = viewName;

    // View containers
    const views = {
        mineracao: document.getElementById('viewMineracao'),
        prospeccao: document.getElementById('viewProspeccao'),
        agenda: document.getElementById('viewAgenda'),
        metricas: document.getElementById('viewMetricas'),
    };

    // Nav tabs
    const tabs = {
        mineracao: document.getElementById('navTabMineracao'),
        prospeccao: document.getElementById('navTabProspeccao'),
        agenda: document.getElementById('navTabAgenda'),
        metricas: document.getElementById('navTabMetricas'),
    };

    // Toggle container display
    Object.keys(views).forEach(key => {
        if (views[key]) {
            if (key === viewName) {
                views[key].classList.remove('hidden');
            } else {
                views[key].classList.add('hidden');
            }
        }
    });

    // Toggle tab active classes
    Object.keys(tabs).forEach(key => {
        if (tabs[key]) {
            if (key === viewName) {
                tabs[key].classList.add('active');
            } else {
                tabs[key].classList.remove('active');
            }
        }
    });

    // View-specific actions
    if (viewName === 'prospeccao') {
        loadLeadsTable();
    } else if (viewName === 'agenda') {
        loadAgendaMeetings();
    } else if (viewName === 'metricas') {
        if (!appState.statusChart || !appState.funnelChart) {
            initCharts();
        }
        loadKpis();
    }
}

function toggleSidebarMenu() {
    const drawer = document.getElementById('sidebarDrawer');
    const overlay = document.getElementById('sidebarOverlay');
    if (!drawer || !overlay) return;

    const isClosed = drawer.classList.contains('translate-x-full');
    if (isClosed) {
        drawer.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
    } else {
        drawer.classList.add('translate-x-full');
        overlay.classList.add('hidden');
    }
}

function setNiche(name) {
    const input = document.getElementById('inputNiche');
    if (input) input.value = name;
}

// ----------------------------------------------------
// CHART.JS INITIALIZATION (HORIZONTAL FUNNEL & DONUT)
// ----------------------------------------------------
function initCharts() {
    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)';

    // Chart 1: Donut Status
    const canvasDonut = document.getElementById('chartStatusDonut');
    if (canvasDonut && !appState.statusChart) {
        const ctxDonut = canvasDonut.getContext('2d');
        appState.statusChart = new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: ['Sem Site', 'Requer Modernização', 'Site Ativo'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#f43f5e', '#f59e0b', '#10b981'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                return ` ${ctx.label}: ${ctx.raw} leads`;
                            }
                        }
                    }
                },
                cutout: '74%'
            }
        });
    }

    // Chart 2: Horizontal Sales Funnel Chart (Substituiu os pontos dispersos)
    const canvasFunnel = document.getElementById('chartFunnel');
    if (canvasFunnel && !appState.funnelChart) {
        const ctxFunnel = canvasFunnel.getContext('2d');
        appState.funnelChart = new Chart(ctxFunnel, {
            type: 'bar',
            data: {
                labels: [
                    '1. Leads Minerados',
                    '2. Oportunidades',
                    '3. Em Contato',
                    '4. Reuniões Agendadas',
                    '5. Fechados (R$ 1.000)'
                ],
                datasets: [{
                    label: 'Leads no Funil',
                    data: [0, 0, 0, 0, 0],
                    backgroundColor: [
                        '#6366f1',
                        '#f59e0b',
                        '#3b82f6',
                        '#8b5cf6',
                        '#10b981'
                    ],
                    borderRadius: 8,
                    barPercentage: 0.65,
                }]
            },
            options: {
                indexAxis: 'y', // Horizontal bars
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                return ` Quantidade: ${ctx.raw} empresas`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: textColor, precision: 0 },
                        grid: { color: gridColor },
                        beginAtZero: true
                    },
                    y: {
                        ticks: { color: textColor, font: { weight: '600' } },
                        grid: { display: false }
                    }
                }
            }
        });
    }
}

function updateChartsTheme() {
    if (!appState.statusChart || !appState.funnelChart) return;
    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)';

    if (appState.funnelChart.options.scales.x) {
        appState.funnelChart.options.scales.x.ticks.color = textColor;
        appState.funnelChart.options.scales.x.grid.color = gridColor;
    }
    if (appState.funnelChart.options.scales.y) {
        appState.funnelChart.options.scales.y.ticks.color = textColor;
    }

    appState.funnelChart.update();
    appState.statusChart.update();
}

// ----------------------------------------------------
// EVENT LISTENERS & FILTERING
// ----------------------------------------------------
function setupEventListeners() {
    document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);
    document.getElementById('btnStartScrape').addEventListener('click', startScrape);
    document.getElementById('btnStopScrape').addEventListener('click', stopScrape);

    document.getElementById('toggleLogsBtn').addEventListener('click', () => {
        const drawer = document.getElementById('terminalDrawer');
        drawer.classList.toggle('hidden');
    });

    // Filters with debounce
    let debounceTimer;
    const filterInputs = ['filterSearch', 'filterStatus', 'filterCrm', 'filterSort'];
    filterInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(loadLeadsTable, 250);
            });
            el.addEventListener('change', loadLeadsTable);
        }
    });
}

// ----------------------------------------------------
// MINING OPERATIONS (START / STOP / SSE)
// ----------------------------------------------------
async function startScrape() {
    const niche = document.getElementById('inputNiche').value.trim();
    const city = document.getElementById('inputCity').value.trim();
    const targetCount = parseInt(document.getElementById('inputTarget').value) || 100;

    if (!niche || !city) {
        showToast('Preencha o Nicho e a Cidade que deseja pesquisar.', 'error');
        return;
    }

    try {
        setUiMiningRunning(true, targetCount);
        addTerminalLog(`Disparando motor Playwright para '${niche}' em '${city}' (Meta: ${targetCount} leads)...`);

        const res = await fetch('/api/scrape/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ niche, city, target_count: targetCount })
        });
        const data = await res.json();

        if (!data.success) {
            showToast(data.error || 'Erro ao iniciar mineração.', 'error');
            setUiMiningRunning(false);
            return;
        }

        showToast(data.message, 'success');
        startPollingStatus();
    } catch (err) {
        showToast('Falha na comunicação com o servidor: ' + err.message, 'error');
        setUiMiningRunning(false);
    }
}

async function stopScrape() {
    try {
        addTerminalLog('Enviando sinal de interrupção para o motor...');
        const res = await fetch('/api/scrape/stop', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast('Interrupção solicitada. Finalizando...', 'info');
        }
    } catch (err) {
        showToast('Erro ao parar: ' + err.message, 'error');
    }
}

function setUiMiningRunning(running, target = 100) {
    appState.isRunning = running;
    const btnStart = document.getElementById('btnStartScrape');
    const btnStop = document.getElementById('btnStopScrape');
    const progressContainer = document.getElementById('liveProgressContainer');
    const engineBadge = document.getElementById('engineStatusBadge');
    const engineText = document.getElementById('engineStatusText');

    if (running) {
        btnStart.classList.add('hidden');
        btnStop.classList.remove('hidden');
        progressContainer.classList.remove('hidden');
        if (engineText) engineText.innerText = 'Minerando...';
        if (engineBadge) engineBadge.querySelector('span:first-child').className = 'w-2 h-2 rounded-full bg-brand-500 animate-ping';
        updateProgressBar(0, target, 'Conectando ao Google Maps...');
    } else {
        btnStart.classList.remove('hidden');
        btnStop.classList.add('hidden');
        if (engineText) engineText.innerText = 'Motor Pronto';
        if (engineBadge) engineBadge.querySelector('span:first-child').className = 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse';
    }
}

function updateProgressBar(count, target, currentLead = '') {
    const bar = document.getElementById('liveProgressBar');
    const progressText = document.getElementById('liveProgressText');
    const currentLeadEl = document.getElementById('liveCurrentLead');

    const pct = target > 0 ? Math.min(100, Math.round((count / target) * 100)) : 0;
    if (bar) bar.style.width = `${pct}%`;
    if (progressText) progressText.innerText = `${count} / ${target} (${pct}%)`;
    if (currentLeadEl && currentLead) currentLeadEl.innerText = currentLead;
}

// ----------------------------------------------------
// SERVER-SENT EVENTS (SSE) STREAMING
// ----------------------------------------------------
function connectSSE() {
    if (appState.eventSource) {
        appState.eventSource.close();
    }

    appState.eventSource = new EventSource('/api/stream');

    appState.eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleSseEvent(data);
        } catch (e) {
            console.error('Erro processando evento SSE:', e);
        }
    };

    appState.eventSource.onerror = () => {
        setTimeout(connectSSE, 5000);
    };
}

function handleSseEvent(data) {
    if (data.type === 'status') {
        updateProgressBar(data.count || 0, appState.targetCount || 100, data.message);
        addTerminalLog(data.message);
    } else if (data.type === 'new_lead') {
        const lead = data.lead;
        updateProgressBar(data.count, data.target, lead.name);
        addTerminalLog(`[NOVO LEAD] ${lead.name} (${lead.phone}) | Score: ${lead.lead_score} | ${lead.qualification_status}`);
        loadKpis();
        loadLeadsTable();
    } else if (data.type === 'finished') {
        setUiMiningRunning(false);
        updateProgressBar(data.count, data.count, 'Varredura Concluída!');
        addTerminalLog(`Mineração concluída com sucesso! ${data.count} leads capturados.`);
        showToast(`Varredura finalizada! ${data.count} leads qualificados prontos.`, 'success');
        loadDashboardData();
    } else if (data.type === 'error') {
        setUiMiningRunning(false);
        addTerminalLog(`[ERRO] ${data.message}`);
        showToast(`Erro na mineração: ${data.message}`, 'error');
    }
}

// Status Poller fallback
let pollerInterval = null;
function startPollingStatus() {
    if (pollerInterval) clearInterval(pollerInterval);
    pollerInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/scrape/status');
            const data = await res.json();
            if (data.is_running) {
                updateProgressBar(data.leads_count, data.target_count, data.current_lead || data.status_message);
            } else if (appState.isRunning && !data.is_running) {
                setUiMiningRunning(false);
                clearInterval(pollerInterval);
                loadDashboardData();
            }
        } catch (e) { }
    }, 2500);
}

function addTerminalLog(text) {
    const logsEl = document.getElementById('terminalLogs');
    const countEl = document.getElementById('terminalCount');
    if (!logsEl) return;

    const time = new Date().toLocaleTimeString('pt-BR');
    const logItem = document.createElement('div');
    logItem.className = 'text-[11px] font-mono text-slate-300 leading-tight';
    logItem.innerHTML = `<span class="text-slate-500">[${time}]</span> ${escapeHtml(text)}`;

    logsEl.appendChild(logItem);
    logsEl.scrollTop = logsEl.scrollHeight;

    if (countEl) {
        countEl.innerText = `${logsEl.children.length} eventos`;
    }
}

// ----------------------------------------------------
// DASHBOARD DATA LOADERS (KPIS, CHARTS, LEADS)
// ----------------------------------------------------
async function loadDashboardData() {
    await Promise.all([loadKpis(), loadLeadsTable(), loadAgendaMeetings()]);
}

async function loadKpis() {
    try {
        const res = await fetch('/api/kpis');
        const data = await res.json();
        if (!data.success) return;

        const k = data.kpis;
        document.getElementById('kpiTotalLeads').innerText = k.total_leads;
        document.getElementById('kpiSemSite').innerText = k.sem_site;
        document.getElementById('kpiModernizacao').innerText = k.modernizacao;

        // Header and drawer leads counters
        const navLeadsCount = document.getElementById('navLeadsCount');
        if (navLeadsCount) navLeadsCount.innerText = k.total_leads;

        const drawerLeadsCount = document.getElementById('drawerLeadsCount');
        if (drawerLeadsCount) drawerLeadsCount.innerText = k.total_leads;

        // Metrics view
        const elMetricPipe = document.getElementById('metricPipeline');
        if (elMetricPipe) elMetricPipe.innerText = `R$ ${k.projecao_faturamento.toLocaleString('pt-BR')}`;

        const elMetricFechados = document.getElementById('metricFechados');
        if (elMetricFechados) elMetricFechados.innerText = k.fechados;

        const elMetricFat = document.getElementById('metricFaturamentoReal');
        if (elMetricFat) elMetricFat.innerText = `R$ ${(k.fechados * 1000).toLocaleString('pt-BR')} faturados`;

        const elMetricQuentes = document.getElementById('metricSuperQuentes');
        if (elMetricQuentes) elMetricQuentes.innerText = k.leads_super_quentes;

        if (document.getElementById('legendSemSite')) {
            document.getElementById('legendSemSite').innerText = k.sem_site;
            document.getElementById('legendModernizacao').innerText = k.modernizacao;
        }

        // Update Charts
        if (appState.statusChart && data.status_chart) {
            appState.statusChart.data.datasets[0].data = data.status_chart.data;
            appState.statusChart.update();
        }

        if (appState.funnelChart && data.funnel_chart) {
            appState.funnelChart.data.datasets[0].data = data.funnel_chart.data;
            appState.funnelChart.update();
        }
    } catch (err) {
        console.error('Erro ao carregar KPIs:', err);
    }
}

async function loadLeadsTable() {
    try {
        const search = document.getElementById('filterSearch').value.trim();
        const status = document.getElementById('filterStatus').value;
        const crm = document.getElementById('filterCrm').value;
        const sort = document.getElementById('filterSort').value;

        const params = new URLSearchParams({
            search: search,
            status: status !== 'all' ? status : (crm !== 'all' ? crm : 'all'),
            sort_by: sort
        });

        const res = await fetch(`/api/leads?${params.toString()}`);
        const data = await res.json();
        if (!data.success) return;

        appState.currentLeads = data.leads;
        renderLeadsTable(data.leads);
        document.getElementById('tableShowingCount').innerText = data.leads.length;
    } catch (err) {
        console.error('Erro ao carregar tabela de leads:', err);
    }
}

function renderLeadsTable(leads) {
    const tbody = document.getElementById('leadsTableBody');
    if (!tbody) return;

    if (!leads || leads.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="py-12 text-center text-slate-400">
                    <i class="ph ph-magnifying-glass text-2xl mb-1"></i>
                    <p class="text-xs">Nenhum lead encontrado com os filtros selecionados.</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = leads.map(lead => {
        // Clean Minimal Score Badge (No Emojis)
        let scoreClass = 'badge-score-normal';
        let priorityLabel = 'Normal';
        if (lead.lead_score >= 80) {
            scoreClass = 'badge-score-high';
            priorityLabel = 'Alta Prioridade';
        } else if (lead.lead_score >= 60) {
            scoreClass = 'badge-score-med';
            priorityLabel = 'Média Prioridade';
        }

        // Qualification Badge
        let qualBadge = '';
        if (lead.qualification_status.includes('Sem Site')) {
            qualBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">Sem Site</span>`;
        } else if (lead.qualification_status.includes('Modernização')) {
            qualBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">Requer Redesign</span>`;
        } else {
            qualBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">Site Ativo</span>`;
        }

        // Scheduled Meeting Badge / Status indicator (with quick remove button)
        let scheduleBadge = '';
        if (lead.scheduled_at) {
            scheduleBadge = `
                <div class="mt-1 inline-flex items-center gap-1.5 text-[11px] font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20" title="${escapeHtml(lead.meeting_notes || '')}">
                    <i class="ph-bold ph-calendar"></i>
                    <span>${escapeHtml(lead.scheduled_at)}</span>
                    <button onclick="unscheduleMeeting(${lead.id})" class="text-rose-500 hover:text-rose-700 ml-0.5" title="Remover da Agenda">
                        <i class="ph-bold ph-x text-[12px]"></i>
                    </button>
                </div>
            `;
        }

        // WhatsApp direct link
        const whatsappBtn = lead.whatsapp_url ? `
            <a href="${lead.whatsapp_url}" target="_blank" class="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500 hover:text-white transition shadow-sm" title="Abrir conversa no WhatsApp">
                <i class="ph-bold ph-whatsapp-logo text-sm"></i>
            </a>
        ` : `
            <button disabled class="p-2 rounded-lg opacity-30 cursor-not-allowed bg-slate-200 dark:bg-darkcard text-slate-400">
                <i class="ph-bold ph-whatsapp-logo text-sm"></i>
            </button>
        `;

        return `
            <tr class="border-b border-slate-100 dark:border-darkborder/50">
                <!-- Score (Sem emojis) -->
                <td class="py-3 px-4 whitespace-nowrap">
                    <div class="flex flex-col gap-0.5">
                        <span class="px-2 py-0.5 rounded-md text-xs font-bold w-max ${scoreClass}">
                            ${lead.lead_score} pts
                        </span>
                        <span class="text-[10px] text-slate-400 font-medium">${priorityLabel}</span>
                    </div>
                </td>

                <!-- Empresa & Local (Nome Completo SEM CORTE & Ajustável) -->
                <td class="py-3 px-4 company-col-cell" style="${getCompanyColWidthStyle()}">
                    <div class="font-bold text-slate-900 dark:text-white leading-normal break-words text-[13px] whitespace-normal">
                        ${escapeHtml(lead.name)}
                    </div>
                    <div class="text-[11px] text-slate-400 break-words flex items-start gap-1 mt-1 leading-snug whitespace-normal">
                        <i class="ph ph-map-pin text-[12px] shrink-0 mt-0.5 text-slate-400"></i>
                        <span>${escapeHtml(lead.address || 'Brasil')}</span>
                    </div>
                </td>

                <!-- Telefone -->
                <td class="py-3 px-4 whitespace-nowrap font-mono text-xs">
                    <div class="flex items-center gap-1.5 text-slate-700 dark:text-slate-200 font-medium">
                        <i class="ph ph-phone text-slate-400"></i>
                        <span>${lead.phone || '<span class="text-slate-400 font-sans">Sem telefone</span>'}</span>
                    </div>
                </td>

                <!-- Google Maps Stats -->
                <td class="py-3 px-4 whitespace-nowrap">
                    <div class="flex items-center gap-1 text-slate-800 dark:text-slate-200 font-bold">
                        <i class="ph-fill ph-star text-amber-400 text-xs"></i>
                        <span>${lead.rating ? lead.rating.toFixed(1) : '0.0'}</span>
                        <span class="text-slate-400 text-[11px] font-normal">(${lead.reviews_count || 0})</span>
                    </div>
                </td>

                <!-- Diagnóstico Web -->
                <td class="py-3 px-4 min-w-[200px] max-w-[300px]">
                    <div class="space-y-0.5">
                        <div>${qualBadge}</div>
                        <div class="text-[10px] text-slate-400 break-words leading-tight" title="${escapeHtml(lead.qualification_detail || '')}">
                            ${escapeHtml(lead.qualification_detail || 'Sem site')}
                        </div>
                    </div>
                </td>

                <!-- Funil CRM & Agenda -->
                <td class="py-3 px-4 whitespace-nowrap">
                    <select onchange="changeLeadCrmStatus(${lead.id}, this.value)" class="px-2 py-1 rounded-lg text-[11px] font-semibold border border-slate-200 dark:border-darkborder bg-white dark:bg-darkcard text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500 cursor-pointer">
                        <option value="Novo" ${lead.crm_status === 'Novo' ? 'selected' : ''}>Novo</option>
                        <option value="Contatado" ${lead.crm_status === 'Contatado' ? 'selected' : ''}>Contatado</option>
                        <option value="Reunião Agendada" ${lead.crm_status === 'Reunião Agendada' ? 'selected' : ''}>Reunião Agendada</option>
                        <option value="Em Negociação" ${lead.crm_status === 'Em Negociação' ? 'selected' : ''}>Em Negociação</option>
                        <option value="Fechado (R$ 1.000)" ${lead.crm_status === 'Fechado (R$ 1.000)' ? 'selected' : ''}>Fechado (R$ 1.000)</option>
                        <option value="Perdido" ${lead.crm_status === 'Perdido' ? 'selected' : ''}>Perdido</option>
                    </select>
                    ${scheduleBadge}
                </td>

                <!-- Ações -->
                <td class="py-3 px-4 whitespace-nowrap text-center">
                    <div class="flex items-center justify-center gap-1.5">
                        <!-- Script Button -->
                        <button onclick="openScriptModal(${lead.id})" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/10 text-brand-600 dark:text-brand-400 hover:bg-brand-500 hover:text-white transition shadow-sm flex items-center gap-1" title="Ver roteiro comercial">
                            <i class="ph-bold ph-phone-call"></i>
                            <span>Script</span>
                        </button>

                        <!-- Agenda Button -->
                        <button onclick="openScheduleModal(${lead.id}, '${escapeHtml(lead.name)}')" class="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-600 hover:text-white transition shadow-sm" title="Agendar Reunião ou Call com o lead">
                            <i class="ph-bold ph-calendar-plus text-sm"></i>
                        </button>

                        <!-- WhatsApp Button -->
                        ${whatsappBtn}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// ----------------------------------------------------
// AGENDA DE REUNIÕES (CARDS, REMOÇÃO & MANAGEMENT)
// ----------------------------------------------------
async function loadAgendaMeetings() {
    try {
        const res = await fetch('/api/meetings');
        const data = await res.json();
        if (!data.success) return;

        const meetings = data.meetings || [];
        const count = meetings.length;

        // Update counters
        const navCount = document.getElementById('navAgendaCount');
        if (navCount) navCount.innerText = count;

        const drawerCount = document.getElementById('drawerAgendaCount');
        if (drawerCount) drawerCount.innerText = count;

        const kpiCount = document.getElementById('kpiAgendados');
        if (kpiCount) kpiCount.innerText = count;

        // Render Agenda Cards
        const container = document.getElementById('agendaCardsContainer');
        if (!container) return;

        if (count === 0) {
            container.innerHTML = `
                <div class="col-span-full py-16 text-center text-slate-400 glass-panel rounded-2xl">
                    <i class="ph ph-calendar-x text-3xl mb-2"></i>
                    <p class="text-sm font-semibold text-slate-700 dark:text-slate-300">Nenhuma reunião agendada no momento.</p>
                    <p class="text-xs text-slate-400 mt-1">Ao prospectar, clique no ícone de calendário ao lado do lead para marcar a call.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = meetings.map(m => {
            return `
                <div class="glass-panel p-5 rounded-2xl space-y-3 relative overflow-hidden border-l-4 border-l-indigo-500">
                    <div class="flex items-start justify-between">
                        <div>
                            <span class="text-[10px] font-bold uppercase tracking-wider text-indigo-500 bg-indigo-500/10 px-2 py-0.5 rounded">
                                Reunião Marcada
                            </span>
                            <h4 class="font-bold text-sm text-slate-900 dark:text-white mt-1.5 break-words">${escapeHtml(m.name)}</h4>
                            <p class="text-xs text-slate-400 font-mono">${m.phone || 'Sem telefone'}</p>
                        </div>
                        <div class="text-right">
                            <span class="text-xs font-extrabold text-indigo-600 dark:text-indigo-400 block">${escapeHtml(m.scheduled_at)}</span>
                            <span class="text-[10px] text-slate-400 break-words">${escapeHtml(m.address || 'Brasil')}</span>
                        </div>
                    </div>

                    ${m.meeting_notes ? `
                        <div class="text-xs p-2.5 rounded-xl bg-slate-50 dark:bg-darkbg text-slate-600 dark:text-slate-300 border border-slate-100 dark:border-darkborder/40">
                            <strong>Pauta:</strong> ${escapeHtml(m.meeting_notes)}
                        </div>
                    ` : ''}

                    <div class="pt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 dark:border-darkborder">
                        <!-- Status Changer -->
                        <div class="flex items-center gap-1.5">
                            <select onchange="handleAgendaStatusChange(${m.id}, this.value)" class="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border border-slate-200 dark:border-darkborder bg-white dark:bg-darkcard text-slate-700 dark:text-slate-200 cursor-pointer">
                                <option value="Reunião Agendada" selected>Status: Agendada</option>
                                <option value="Fechado (R$ 1.000)">Fechado (R$ 1.000)</option>
                                <option value="Em Negociação">Em Negociação</option>
                                <option value="Perdido">Perdido (Remover)</option>
                                <option value="Cancelar Reunião">Cancelar Reunião</option>
                            </select>
                        </div>

                        <div class="flex items-center gap-1.5">
                            <!-- Button: Remove / Unschedule Meeting -->
                            <button onclick="unscheduleMeeting(${m.id})" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-rose-600 dark:text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/25 flex items-center gap-1 transition" title="Remover da Agenda">
                                <i class="ph-bold ph-calendar-x text-sm"></i>
                                <span>Remover</span>
                            </button>
                            
                            <!-- Button: WhatsApp Direct -->
                            ${m.whatsapp_url ? `
                                <a href="${m.whatsapp_url}" target="_blank" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-500 flex items-center gap-1 transition shadow-sm">
                                    <i class="ph-bold ph-whatsapp-logo text-sm"></i>
                                    <span>WhatsApp</span>
                                </a>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error('Erro ao carregar agenda:', err);
    }
}

// Schedule Modal open/close/save
function openScheduleModal(leadId, leadName) {
    appState.schedulingLeadId = leadId;
    document.getElementById('scheduleCompanyName').innerText = leadName;

    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0];
    document.getElementById('scheduleDateInput').value = dateStr;
    document.getElementById('scheduleTimeInput').value = '14:30';
    document.getElementById('scheduleNotesInput').value = 'Apresentação da proposta de Landing Page (R$ 1.000,00)';

    document.getElementById('scheduleModal').classList.remove('hidden');
}

function closeScheduleModal() {
    document.getElementById('scheduleModal').classList.add('hidden');
    appState.schedulingLeadId = null;
}

async function saveMeetingSchedule() {
    if (!appState.schedulingLeadId) return;

    const date = document.getElementById('scheduleDateInput').value;
    const time = document.getElementById('scheduleTimeInput').value;
    const notes = document.getElementById('scheduleNotesInput').value.trim();

    if (!date || !time) {
        showToast('Informe a data e o horário da reunião.', 'error');
        return;
    }

    const scheduled_at = `${date} às ${time}`;

    try {
        const res = await fetch(`/api/lead/${appState.schedulingLeadId}/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scheduled_at, meeting_notes: notes })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Reunião agendada para ${scheduled_at}!`, 'success');
            closeScheduleModal();
            loadLeadsTable();
            loadAgendaMeetings();
            loadKpis();
        } else {
            showToast(data.error || 'Erro ao agendar.', 'error');
        }
    } catch (err) {
        showToast('Erro de comunicação: ' + err.message, 'error');
    }
}

async function handleAgendaStatusChange(leadId, newStatus) {
    if (newStatus === 'Cancelar Reunião' || newStatus === 'Perdido') {
        await unscheduleMeeting(leadId, false);
        return;
    }
    await changeLeadCrmStatus(leadId, newStatus);
    loadAgendaMeetings();
}

async function unscheduleMeeting(leadId, askConfirm = true) {
    if (askConfirm && !confirm('Deseja realmente remover esta reunião da agenda?')) return;

    try {
        const res = await fetch(`/api/lead/${leadId}/unschedule`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast('Reunião removida da agenda com sucesso!', 'success');
            loadAgendaMeetings();
            loadLeadsTable();
            loadKpis();
        } else {
            showToast('Erro ao remover reunião.', 'error');
        }
    } catch (err) {
        showToast('Erro ao remover reunião: ' + err.message, 'error');
    }
}


// ----------------------------------------------------
// CLEAR DATABASE CONFIRMATION & EXECUTION
// ----------------------------------------------------
function confirmClearLeads() {
    document.getElementById('clearConfirmModal').classList.remove('hidden');
}

function closeClearModal() {
    document.getElementById('clearConfirmModal').classList.add('hidden');
}

async function executeClearLeads() {
    try {
        const res = await fetch('/api/leads/clear', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast('Base de leads e histórico limpos com sucesso!', 'success');
            closeClearModal();
            loadDashboardData();
        } else {
            showToast('Erro ao limpar base.', 'error');
        }
    } catch (err) {
        showToast('Erro de comunicação: ' + err.message, 'error');
    }
}

// ----------------------------------------------------
// CRM STATUS & SCRIPT MODAL ACTIONS
// ----------------------------------------------------
async function changeLeadCrmStatus(leadId, newStatus) {
    try {
        const res = await fetch(`/api/lead/${leadId}/crm_status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Status atualizado para '${newStatus}'!`, 'success');
            loadKpis();
        }
    } catch (err) {
        showToast('Erro ao atualizar status: ' + err.message, 'error');
    }
}

async function openScriptModal(leadId) {
    try {
        const res = await fetch(`/api/lead/${leadId}/script`);
        const data = await res.json();
        if (!data.success) {
            showToast('Erro ao carregar roteiro do lead.', 'error');
            return;
        }

        const lead = data.lead;
        appState.activeLeadData = data;

        document.getElementById('modalCompanyName').innerText = lead.name;
        document.getElementById('modalSubtitle').innerText = `${lead.qualification_status} • Score: ${lead.lead_score} pts • ${lead.phone || 'Sem telefone'}`;
        document.getElementById('modalColdCallText').value = data.cold_call_script;
        document.getElementById('modalWhatsAppText').value = data.whatsapp_script;

        const wpLink = document.getElementById('modalWhatsAppLink');
        if (data.whatsapp_url) {
            wpLink.href = data.whatsapp_url;
            wpLink.classList.remove('hidden');
        } else {
            wpLink.classList.add('hidden');
        }

        switchModalTab('coldcall');
        document.getElementById('scriptModal').classList.remove('hidden');
    } catch (err) {
        showToast('Erro ao abrir script: ' + err.message, 'error');
    }
}

function closeScriptModal() {
    document.getElementById('scriptModal').classList.add('hidden');
}

function switchModalTab(tab) {
    const tabCold = document.getElementById('tabColdCallBtn');
    const tabWp = document.getElementById('tabWhatsAppBtn');
    const contentCold = document.getElementById('modalColdCallContent');
    const contentWp = document.getElementById('modalWhatsAppContent');

    if (tab === 'coldcall') {
        tabCold.className = 'pb-2 border-b-2 border-brand-500 text-brand-600 dark:text-brand-400 flex items-center gap-1.5';
        tabWp.className = 'pb-2 border-b-2 border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-white flex items-center gap-1.5';
        contentCold.classList.remove('hidden');
        contentWp.classList.add('hidden');
    } else {
        tabCold.className = 'pb-2 border-b-2 border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-white flex items-center gap-1.5';
        tabWp.className = 'pb-2 border-b-2 border-emerald-500 text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5';
        contentCold.classList.add('hidden');
        contentWp.classList.remove('hidden');
    }
}

function copyToClipboard(elementId) {
    const textEl = document.getElementById(elementId);
    if (!textEl) return;
    textEl.select();
    navigator.clipboard.writeText(textEl.value).then(() => {
        showToast('Copiado para a área de transferência!', 'success');
    }).catch(() => {
        document.execCommand('copy');
        showToast('Copiado com sucesso!', 'success');
    });
}

// ----------------------------------------------------
// TOAST NOTIFICATIONS & UTILITIES
// ----------------------------------------------------
function showToast(message, type = 'info') {
    const toast = document.getElementById('toastNotification');
    const toastMsg = document.getElementById('toastMessage');
    const toastIcon = document.getElementById('toastIcon');
    if (!toast) return;

    toastMsg.innerText = message;
    if (type === 'success') {
        toast.className = 'fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl shadow-xl text-xs font-semibold flex items-center gap-2 bg-emerald-600 text-white animate-in slide-in-from-bottom-5';
        toastIcon.className = 'ph-bold ph-check-circle text-base';
    } else if (type === 'error') {
        toast.className = 'fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl shadow-xl text-xs font-semibold flex items-center gap-2 bg-rose-600 text-white animate-in slide-in-from-bottom-5';
        toastIcon.className = 'ph-bold ph-warning-circle text-base';
    } else {
        toast.className = 'fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl shadow-xl text-xs font-semibold flex items-center gap-2 bg-brand-600 text-white animate-in slide-in-from-bottom-5';
        toastIcon.className = 'ph-bold ph-info text-base';
    }

    toast.classList.remove('hidden');
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3500);
}

function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return text.toString().replace(/[&<>"']/g, m => map[m]);
}
