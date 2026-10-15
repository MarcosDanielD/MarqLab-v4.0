/**
 * Marq Lab - Modern B2B Growth Engine Frontend (v5.0)
 * Features:
 * - Collapsible Left Sidebar (Hamburger Toggle + LocalStorage memory)
 * - Multi-Operator / SDR Team Management (Default: Jamilly, Marcos, dynamic SDRs)
 * - Direct Lead Reassignment per SDR
 * - Contact Type Visual Badges (Celular / WhatsApp vs Linha Fixa)
 * - 1-Click Commercial Proposal in PDF & Text (R$ 1.000 / Landing Page)
 * - Interaction Notes & Call History Timeline per Lead
 * - Today's Meetings Top Banner Alert
 * - Multi-Step Outreach Cadence (Cold Call, WhatsApp 1, Follow-up D+2, Follow-up D+5)
 * - Adjustable Company Name Column Width
 * - Horizontal Sales Funnel Chart & Diagnostic Donut Chart
 */

// Global Application State
let appState = {
    theme: localStorage.getItem('marq_theme') || 'light',
    companyWidthMode: localStorage.getItem('marq_company_width') || 'normal',
    sidebarCollapsed: localStorage.getItem('marq_sidebar_collapsed') === 'true',
    currentUser: null,
    activeOperator: localStorage.getItem('marq_active_operator') || 'Jamilly',
    currentView: 'mineracao',
    isRunning: false,
    currentLeads: [],
    operators: [],
    statusChart: null,
    funnelChart: null,
    eventSource: null,
    activeLeadData: null,
    schedulingLeadId: null,
    activeNotesLeadId: null,
    activeProposalLead: null,
};

// DOM Ready initialization
document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    initSidebarState();
    initCompanyWidth();
    setupEventListeners();
    const isAuthed = await checkAuth();
    if (!isAuthed) return;
    loadOperators();
    loadDashboardData();
    loadTodaysMeetings();
    connectSSE();
    startPresenceHeartbeat();
});

// ----------------------------------------------------
// 0. AUTHENTICATION & MULTI-USER SESSION CONTROLLER
// ----------------------------------------------------
async function checkAuth() {
    try {
        const res = await fetch('/api/auth/me');
        if (res.status === 401) {
            window.location.href = '/login';
            return false;
        }
        const data = await res.json();
        if (data.success && data.user) {
            appState.currentUser = data.user;
            appState.activeOperator = data.user.name;
            updateUserSessionUi(data.user);
            return true;
        } else {
            window.location.href = '/login';
            return false;
        }
    } catch (e) {
        console.error('Erro verificando autenticação:', e);
        return false;
    }
}

async function handleLogout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (e) {
        window.location.href = '/login';
    }
}

function updateUserSessionUi(user) {
    if (!user) return;
    const name = user.name || 'Operador';
    const initial = name.charAt(0).toUpperCase();
    const role = user.role || (user.permission_level === 'ADMIN' ? 'Gestor' : 'SDR');
    const isAdmin = (user.permission_level === 'ADMIN');

    // Sidebar
    const sideAvatar = document.getElementById('sidebarOperatorAvatar');
    if (sideAvatar) sideAvatar.innerText = initial;

    const sideName = document.getElementById('sidebarOperatorName');
    if (sideName) sideName.innerText = name;

    const sideRole = document.getElementById('sidebarOperatorRole');
    if (sideRole) sideRole.innerText = role;

    const sideBadge = document.getElementById('sidebarOperatorRoleBadge');
    if (sideBadge) {
        sideBadge.innerText = isAdmin ? 'Admin' : 'SDR';
        sideBadge.className = isAdmin
            ? 'px-1 py-0.2 rounded text-[8px] font-bold uppercase tracking-wider bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900'
            : 'px-1 py-0.2 rounded text-[8px] font-bold uppercase tracking-wider bg-stone-200 dark:bg-darkborder text-stone-700 dark:text-stone-300';
    }

    // Top Header
    const headerName = document.getElementById('headerOperatorName');
    if (headerName) headerName.innerText = name;

    const headerBadge = document.getElementById('headerOperatorPermBadge');
    if (headerBadge) {
        headerBadge.innerText = isAdmin ? 'Gestor' : 'SDR';
        headerBadge.className = isAdmin
            ? 'ml-0.5 px-1 py-0.2 rounded text-[9px] font-bold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 border border-stone-900 dark:border-stone-100 uppercase'
            : 'ml-0.5 px-1 py-0.2 rounded text-[9px] font-bold bg-stone-200 dark:bg-darkcard2 text-stone-700 dark:text-stone-300 border border-stone-300 dark:border-darkborder uppercase';
    }
}

let presenceInterval = null;
function startPresenceHeartbeat() {
    if (presenceInterval) clearInterval(presenceInterval);
    const ping = async () => {
        try {
            await fetch('/api/presence/ping', { method: 'POST' });
        } catch (e) { }
    };
    ping();
    presenceInterval = setInterval(ping, 25000);
}

// ----------------------------------------------------
// 1. SIDEBAR COLLAPSIBLE CONTROLLER (MENU ESQUERDO)
// ----------------------------------------------------
function initSidebarState() {
    if (appState.sidebarCollapsed) {
        document.body.classList.add('sidebar-collapsed');
    } else {
        document.body.classList.remove('sidebar-collapsed');
    }
}

function toggleSidebarCollapse() {
    // If mobile screen (< 1024px)
    if (window.innerWidth < 1024) {
        const isOpen = document.body.classList.toggle('sidebar-mobile-open');
        const backdrop = document.getElementById('sidebarBackdrop');
        if (backdrop) {
            if (isOpen) {
                backdrop.classList.remove('hidden');
            } else {
                backdrop.classList.add('hidden');
            }
        }
        return;
    }

    // Desktop: toggle class on body
    const isCollapsed = document.body.classList.toggle('sidebar-collapsed');
    appState.sidebarCollapsed = isCollapsed;
    localStorage.setItem('marq_sidebar_collapsed', isCollapsed ? 'true' : 'false');

    // Trigger chart resize if visible
    setTimeout(() => {
        if (appState.funnelChart) appState.funnelChart.resize();
        if (appState.statusChart) appState.statusChart.resize();
    }, 320);
}

// ----------------------------------------------------
// 2. COLUMN WIDTH CONTROLLER (NOME DA EMPRESA)
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
                btn.className = 'px-2 py-0.5 rounded text-[10px] font-bold border border-stone-900 bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 shadow-sm';
            } else {
                btn.className = 'px-2 py-0.5 rounded text-[10px] font-medium border border-stone-200 dark:border-darkborder bg-white dark:bg-darkcard text-stone-600 dark:text-stone-300 hover:border-stone-400 transition';
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
// 3. THEME SWITCHER
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
// 4. VIEW NAVIGATION SWITCHER (4 MENUS DEDICADOS)
// ----------------------------------------------------
function switchView(viewName) {
    appState.currentView = viewName;

    // View containers
    const views = {
        mineracao: document.getElementById('viewMineracao'),
        radar_cnpj: document.getElementById('viewRadarCnpj'),
        instagram: document.getElementById('viewInstagram'),
        prospeccao: document.getElementById('viewProspeccao'),
        agenda: document.getElementById('viewAgenda'),
        metricas: document.getElementById('viewMetricas'),
    };

    // Sidebar items
    const sideNavs = {
        mineracao: document.getElementById('sideNavMineracao'),
        radar_cnpj: document.getElementById('sideNavRadarCnpj'),
        instagram: document.getElementById('sideNavInstagram'),
        prospeccao: document.getElementById('sideNavProspeccao'),
        agenda: document.getElementById('sideNavAgenda'),
        metricas: document.getElementById('sideNavMetricas'),
    };

    // Update Header Title
    const headerTitle = document.getElementById('headerViewTitle');
    const titleMap = {
        mineracao: 'Robô de Mineração Maps',
        radar_cnpj: 'Radar de CNPJs Recém-Abertos',
        instagram: 'Auditor de Links no Instagram',
        prospeccao: 'Central de Leads & Prospecção',
        agenda: 'Agenda de Reuniões & Follow-ups',
        metricas: 'Métricas & Funil Comercial'
    };
    if (headerTitle && titleMap[viewName]) {
        headerTitle.innerText = titleMap[viewName];
    }

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

    // Toggle sidebar active styles
    Object.keys(sideNavs).forEach(key => {
        if (sideNavs[key]) {
            if (key === viewName) {
                sideNavs[key].classList.add('active');
            } else {
                sideNavs[key].classList.remove('active');
            }
        }
    });

    // On mobile, close sidebar after clicking nav item
    if (window.innerWidth < 1024) {
        document.body.classList.remove('sidebar-mobile-open');
        const backdrop = document.getElementById('sidebarBackdrop');
        if (backdrop) backdrop.classList.add('hidden');
    }

    // View-specific refreshes
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

function setNiche(name) {
    const input = document.getElementById('inputNiche');
    if (input) input.value = name;
}

// ----------------------------------------------------
// 5. SDR & OPERATOR MANAGEMENT
// ----------------------------------------------------
async function loadOperators() {
    try {
        const res = await fetch('/api/operators');
        const data = await res.json();
        if (!data.success) return;

        appState.operators = data.operators || [];

        // 1. Update Sidebar Operator Select
        const selActive = document.getElementById('selectActiveOperator');
        if (selActive) {
            selActive.innerHTML = appState.operators.map(op => {
                const isSelected = op.name === appState.activeOperator;
                return `<option value="${escapeHtml(op.name)}" ${isSelected ? 'selected' : ''}>${escapeHtml(op.name)} (${escapeHtml(op.role || 'SDR')})</option>`;
            }).join('');
        }

        // 2. Update Leads Table SDR Filter
        const filterOp = document.getElementById('filterOperator');
        if (filterOp) {
            const currentFilterVal = filterOp.value;
            filterOp.innerHTML = `
                <option value="all">SDR: Todos</option>
                ${appState.operators.map(op => `<option value="${escapeHtml(op.name)}">SDR: ${escapeHtml(op.name)}</option>`).join('')}
                <option value="unassigned">Sem Atribuição</option>
            `;
            if (currentFilterVal) filterOp.value = currentFilterVal;
        }

        // 3. Update Header & Avatar
        updateActiveOperatorUi(appState.activeOperator);

        // 4. Update Team Modal list
        renderOperatorsModalList();
    } catch (err) {
        console.error('Erro ao carregar operadores:', err);
    }
}

function getActiveOperatorPermission() {
    const currentOp = appState.operators.find(o => o.name === appState.activeOperator);
    return currentOp ? (currentOp.permission_level || 'SDR') : (appState.activeOperator === 'Marcos' ? 'ADMIN' : 'SDR');
}

function updateActiveOperatorUi(name) {
    const headerOp = document.getElementById('headerOperatorName');
    if (headerOp) headerOp.innerText = name;

    const avatar = document.getElementById('sidebarOperatorAvatar');
    if (avatar) avatar.innerText = name.charAt(0).toUpperCase();

    const currentOp = appState.operators.find(o => o.name === name);
    const permLevel = currentOp ? (currentOp.permission_level || 'SDR') : (name === 'Marcos' ? 'ADMIN' : 'SDR');

    const permBadge = document.getElementById('headerOperatorPermBadge');
    if (permBadge) {
        if (permLevel === 'ADMIN') {
            permBadge.innerText = 'Gestor';
            permBadge.className = 'ml-0.5 px-1 py-0.5 rounded text-[9px] font-bold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 border border-stone-900 dark:border-stone-100 uppercase';
        } else {
            permBadge.innerText = 'SDR';
            permBadge.className = 'ml-0.5 px-1 py-0.5 rounded text-[9px] font-bold bg-stone-200 dark:bg-darkcard2 text-stone-700 dark:text-stone-300 border border-stone-300 dark:border-darkborder uppercase';
        }
    }
}

function changeActiveOperator(opName) {
    appState.activeOperator = opName;
    localStorage.setItem('marq_active_operator', opName);
    updateActiveOperatorUi(opName);
    const perm = getActiveOperatorPermission();
    showToast(`Operador alterado para ${opName} (${perm === 'ADMIN' ? 'Gestor' : 'SDR'})`, 'info');
}

function openTeamModal() {
    renderOperatorsModalList();
    document.getElementById('teamModal').classList.remove('hidden');
}

function closeTeamModal() {
    document.getElementById('teamModal').classList.add('hidden');
}

function renderOperatorsModalList() {
    const container = document.getElementById('operatorsListContainer');
    if (!container) return;

    if (!appState.operators || appState.operators.length === 0) {
        container.innerHTML = `<div class="text-xs text-stone-400 p-2 text-center">Nenhum operador cadastrado.</div>`;
        return;
    }

    const currentUserName = appState.currentUser ? appState.currentUser.name : '';
    const isCurrentUserAdmin = appState.currentUser && appState.currentUser.permission_level === 'ADMIN';

    container.innerHTML = appState.operators.map(op => {
        const isCurrent = op.name === currentUserName;
        const isAdmin = (op.permission_level || 'SDR') === 'ADMIN';
        const badgeRole = isAdmin
            ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900">Gestor</span>`
            : `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-stone-200 dark:bg-darkcard2 text-stone-700 dark:text-stone-300 border border-stone-300 dark:border-darkborder">SDR</span>`;

        return `
            <div class="p-2.5 rounded-xl border border-stone-200 dark:border-darkborder bg-white dark:bg-darkcard flex items-center justify-between text-xs gap-2">
                <div class="flex items-center gap-2 min-w-0">
                    <div class="w-7 h-7 rounded-md ${isAdmin ? 'bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900' : 'bg-stone-200 text-stone-700 dark:bg-darkcard2 dark:text-stone-300'} font-bold flex items-center justify-center text-xs shrink-0">
                        ${op.name.charAt(0).toUpperCase()}
                    </div>
                    <div class="min-w-0 truncate">
                        <div class="flex items-center gap-1.5 truncate">
                            <strong class="text-stone-900 dark:text-white truncate">${escapeHtml(op.name)}</strong>
                            ${badgeRole}
                        </div>
                        <div class="text-[10px] text-stone-400 truncate flex items-center gap-1">
                            <span>${escapeHtml(op.email || 'Sem e-mail cadastrado')}</span>
                        </div>
                    </div>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                    ${isCurrent ? `
                        <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900/40">Você</span>
                    ` : (isCurrentUserAdmin ? `
                        <button onclick="deactivateOperator(${op.id}, '${escapeHtml(op.name)}')" class="px-2 py-0.5 rounded text-[10px] font-medium text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition border border-rose-200 dark:border-rose-900/40" title="Desativar membro da equipe">
                            Desativar
                        </button>
                    ` : '')}
                </div>
            </div>
        `;
    }).join('');
}

async function saveNewOperator() {
    const nameInput = document.getElementById('newOperatorName');
    const roleInput = document.getElementById('newOperatorRole');
    const emailInput = document.getElementById('newOperatorEmail');
    const pwdInput = document.getElementById('newOperatorPassword');
    const permSelect = document.getElementById('newOperatorPermLevel');

    const name = nameInput ? nameInput.value.trim() : '';
    const role = roleInput ? roleInput.value.trim() || 'SDR / Vendas' : 'SDR / Vendas';
    const email = emailInput ? emailInput.value.trim() : '';
    const password = pwdInput ? pwdInput.value.trim() : '';
    const permission_level = permSelect ? permSelect.value : 'SDR';

    if (!name) {
        showToast('Informe o nome do vendedor/operador.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/operators', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, role, email, password, permission_level })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Operador ${name} (${permission_level}) cadastrado com sucesso!`, 'success');
            if (nameInput) nameInput.value = '';
            if (emailInput) emailInput.value = '';
            if (pwdInput) pwdInput.value = '';
            await loadOperators();
        } else {
            showToast(data.error || 'Erro ao cadastrar operador.', 'error');
        }
    } catch (err) {
        showToast('Erro de comunicação: ' + err.message, 'error');
    }
}

async function deactivateOperator(opId, opName) {
    if (!confirm(`Deseja realmente desativar o acesso de ${opName}?`)) return;
    try {
        const res = await fetch(`/api/operator/${opId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(`Membro ${opName} desativado.`, 'success');
            await loadOperators();
        } else {
            showToast(data.error || 'Erro ao desativar membro.', 'error');
        }
    } catch (err) {
        showToast('Erro: ' + err.message, 'error');
    }
}

async function claimLead(leadId) {
    try {
        const res = await fetch(`/api/lead/${leadId}/claim`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast('Você assumiu este lead com sucesso!', 'success');
            loadLeadsTable();
            loadKpis();
        } else {
            showToast(data.error || 'Não foi possível assumir este lead.', 'error');
        }
    } catch (err) {
        showToast('Erro ao assumir lead: ' + err.message, 'error');
    }
}

async function changeLeadOperator(leadId, opName) {
    try {
        const res = await fetch(`/api/lead/${leadId}/assign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operator: opName })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Lead atribuído a ${opName}!`, 'success');
        } else {
            showToast(data.error || 'Erro ao transferir lead.', 'error');
            loadLeadsTable();
        }
    } catch (err) {
        showToast('Erro ao atribuir operador: ' + err.message, 'error');
        loadLeadsTable();
    }
}

// ----------------------------------------------------
// 6. TODAY'S MEETINGS ALERT BANNER
// ----------------------------------------------------
async function loadTodaysMeetings() {
    try {
        const res = await fetch('/api/meetings/today');
        const data = await res.json();
        if (!data.success) return;

        const banner = document.getElementById('headerTodayBanner');
        const text = document.getElementById('headerTodayText');
        if (!banner || !text) return;

        const meetings = data.meetings || [];
        if (meetings.length > 0) {
            text.innerText = `${meetings.length} reunião(ões) hoje!`;
            banner.classList.remove('hidden');
        } else {
            banner.classList.add('hidden');
        }
    } catch (err) {
        console.error('Erro ao verificar reuniões de hoje:', err);
    }
}

// ----------------------------------------------------
// 7. CHART.JS INITIALIZATION (HORIZONTAL FUNNEL & DONUT)
// ----------------------------------------------------
function initCharts() {
    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#A8A29A' : '#78716C';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)';

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
                    backgroundColor: ['#C2410C', '#D97706', '#15803D'],
                    borderWidth: 0,
                    hoverOffset: 3
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

    // Chart 2: Horizontal Sales Funnel Chart
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
                        '#1C1917',
                        '#57534E',
                        '#78716C',
                        '#D97706',
                        '#15803D'
                    ],
                    borderRadius: 6,
                    barPercentage: 0.6,
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
                        ticks: { color: textColor, precision: 0, font: { size: 10 } },
                        grid: { color: gridColor },
                        beginAtZero: true
                    },
                    y: {
                        ticks: { color: textColor, font: { weight: '600', size: 10.5 } },
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
    const textColor = isDark ? '#A8A29A' : '#78716C';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)';

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
// 8. EVENT LISTENERS & FILTERING
// ----------------------------------------------------
function setupEventListeners() {
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

    const btnStart = document.getElementById('btnStartScrape');
    if (btnStart) btnStart.addEventListener('click', startScrape);

    const btnStop = document.getElementById('btnStopScrape');
    if (btnStop) btnStop.addEventListener('click', stopScrape);

    const logsBtn = document.getElementById('toggleLogsBtn');
    if (logsBtn) {
        logsBtn.addEventListener('click', () => {
            const drawer = document.getElementById('terminalDrawer');
            if (drawer) drawer.classList.toggle('hidden');
        });
    }

    // Filter inputs with debounce
    let debounceTimer;
    const filterInputs = ['filterSearch', 'filterStatus', 'filterCrm', 'filterOperator', 'filterPhoneType', 'filterCnpj', 'filterSort'];
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
// 9. MINING OPERATIONS (START / STOP / SSE)
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
        if (btnStart) btnStart.classList.add('hidden');
        if (btnStop) btnStop.classList.remove('hidden');
        if (progressContainer) progressContainer.classList.remove('hidden');
        if (engineText) engineText.innerText = 'Minerando...';
        if (engineBadge) engineBadge.querySelector('span:first-child').className = 'w-2 h-2 rounded-full bg-brand-500 animate-ping';
        updateProgressBar(0, target, 'Conectando ao Google Maps...');
    } else {
        if (btnStart) btnStart.classList.remove('hidden');
        if (btnStop) btnStop.classList.add('hidden');
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
// 10. SERVER-SENT EVENTS (SSE) STREAMING
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
    } else if (data.type === 'lead_status_changed') {
        loadKpis();
        loadLeadsTable();
        const myName = appState.currentUser ? appState.currentUser.name : '';
        if (data.operator && data.operator !== myName) {
            showToast(`[${data.operator}] alterou status do Lead #${data.lead_id} para '${data.new_status}'`, 'info');
        }
    } else if (data.type === 'lead_claimed') {
        loadLeadsTable();
        loadKpis();
        const myName = appState.currentUser ? appState.currentUser.name : '';
        if (data.assigned_to && data.assigned_to !== myName) {
            showToast(`[${data.assigned_to}] assumiu o lead "${data.lead_name || '#' + data.lead_id}"`, 'info');
        }
    } else if (data.type === 'lead_assigned' || data.type === 'leads_bulk_assigned') {
        loadLeadsTable();
        loadKpis();
    } else if (data.type === 'meeting_scheduled' || data.type === 'meeting_unscheduled') {
        loadAgendaMeetings();
        loadTodaysMeetings();
        loadLeadsTable();
        loadKpis();
        const myName = appState.currentUser ? appState.currentUser.name : '';
        if (data.type === 'meeting_scheduled' && data.operator && data.operator !== myName) {
            showToast(`[${data.operator}] agendou reunião com ${data.lead_name || 'lead'} para ${data.scheduled_at}`, 'info');
        }
    } else if (data.type === 'lead_note_added') {
        if (appState.activeNotesLeadId == data.lead_id) {
            fetch(`/api/lead/${data.lead_id}/notes`).then(r => r.json()).then(d => {
                if (d.success) renderNotesList(d.notes || []);
            });
        }
        loadLeadsTable();
    } else if (data.type === 'database_cleared') {
        showToast(`Base de leads limpa pelo administrador [${data.operator}].`, 'warning');
        loadDashboardData();
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
// 11. DASHBOARD DATA LOADERS (KPIS, CHARTS, LEADS)
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
        const totalLeadsEl = document.getElementById('kpiTotalLeads');
        if (totalLeadsEl) totalLeadsEl.innerText = k.total_leads;

        const semSiteEl = document.getElementById('kpiSemSite');
        if (semSiteEl) semSiteEl.innerText = k.sem_site;

        const modEl = document.getElementById('kpiModernizacao');
        if (modEl) modEl.innerText = k.modernizacao;

        // Sidebar count
        const sideLeadsCount = document.getElementById('sideLeadsCount');
        if (sideLeadsCount) sideLeadsCount.innerText = k.total_leads;

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
        const search = document.getElementById('filterSearch') ? document.getElementById('filterSearch').value.trim() : '';
        const status = document.getElementById('filterStatus') ? document.getElementById('filterStatus').value : 'all';
        const crm = document.getElementById('filterCrm') ? document.getElementById('filterCrm').value : 'all';
        const operator = document.getElementById('filterOperator') ? document.getElementById('filterOperator').value : 'all';
        const phoneType = document.getElementById('filterPhoneType') ? document.getElementById('filterPhoneType').value : 'all';
        const cnpjFilter = document.getElementById('filterCnpj') ? document.getElementById('filterCnpj').value : 'all';
        const sort = document.getElementById('filterSort') ? document.getElementById('filterSort').value : 'score_desc';

        const params = new URLSearchParams({
            search: search,
            status: status !== 'all' ? status : (crm !== 'all' ? crm : 'all'),
            operator: operator,
            phone_type: phoneType,
            cnpj_filter: cnpjFilter,
            sort_by: sort
        });

        const res = await fetch(`/api/leads?${params.toString()}`);
        const data = await res.json();
        if (!data.success) return;

        appState.currentLeads = data.leads;
        renderLeadsTable(data.leads);
        const countSpan = document.getElementById('tableShowingCount');
        if (countSpan) countSpan.innerText = data.leads.length;
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
                <td colspan="8" class="py-12 text-center text-slate-400">
                    <i class="ph ph-magnifying-glass text-2xl mb-1"></i>
                    <p class="text-xs">Nenhum lead encontrado com os filtros selecionados.</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = leads.map(lead => {
        // Score Badge
        let scoreClass = 'badge-score-normal';
        let priorityLabel = 'Normal';
        if (lead.lead_score >= 80) {
            scoreClass = 'badge-score-high';
            priorityLabel = 'Alta Prioridade';
        } else if (lead.lead_score >= 60) {
            scoreClass = 'badge-score-med';
            priorityLabel = 'Média';
        }

        // Qualification Badge - Warm Minimalist
        let qualBadge = '';
        if (lead.qualification_status.includes('Sem Site')) {
            qualBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#FFF7ED] text-[#9A3412] border border-[#FFEDD5]">Sem Site</span>`;
        } else if (lead.qualification_status.includes('Modernização')) {
            qualBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#FEFCE8] text-[#854D0E] border border-[#FEF08A]">Requer Redesign</span>`;
        } else {
            qualBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#F0FDF4] text-[#166534] border border-[#DCFCE7]">Site Ativo</span>`;
        }

        // Phone Type Badge
        let phoneTypeBadge = '';
        const pType = lead.phone_type || 'whatsapp';
        if (pType === 'whatsapp') {
            phoneTypeBadge = `
                <span class="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[9px] font-medium bg-[#F0FDF4] text-[#166534] border border-[#DCFCE7]">
                    <i class="ph-bold ph-whatsapp-logo text-[10px]"></i> Whats
                </span>
            `;
        } else if (pType === 'landline') {
            phoneTypeBadge = `
                <span class="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[9px] font-medium bg-stone-100 dark:bg-darkborder text-stone-500 dark:text-stone-400">
                    <i class="ph-bold ph-phone text-[10px]"></i> Fixo
                </span>
            `;
        }

        // Scheduled Meeting Badge
        let scheduleBadge = '';
        if (lead.scheduled_at) {
            scheduleBadge = `
                <div class="mt-1 inline-flex items-center gap-1.5 text-[10px] font-semibold text-stone-900 dark:text-white bg-stone-100 dark:bg-darkborder px-1.5 py-0.5 rounded border border-stone-200 dark:border-darkborder" title="${escapeHtml(lead.meeting_notes || '')}">
                    <i class="ph-bold ph-calendar text-[11px]"></i>
                    <span>${escapeHtml(lead.scheduled_at)}</span>
                    <button onclick="unscheduleMeeting(${lead.id})" class="text-stone-400 hover:text-rose-600 ml-0.5" title="Remover da Agenda">
                        <i class="ph-bold ph-x text-[10px]"></i>
                    </button>
                </div>
            `;
        }

        // Notes count badge
        const notesCount = (lead.notes && Array.isArray(lead.notes)) ? lead.notes.length : (lead.notes_count || 0);
        const notesBadge = notesCount > 0 ? `
            <span class="ml-1 px-1.5 py-0.2 rounded-full text-[9px] font-bold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900">${notesCount}</span>
        ` : '';

        // WhatsApp direct link button
        const whatsappBtn = lead.whatsapp_url ? `
            <a href="${lead.whatsapp_url}" target="_blank" class="p-1.5 rounded-lg bg-[#15803D] text-white hover:bg-[#166534] transition shadow-sm" title="Abrir conversa no WhatsApp">
                <i class="ph-bold ph-whatsapp-logo text-xs"></i>
            </a>
        ` : `
            <button disabled class="p-1.5 rounded-lg opacity-30 cursor-not-allowed bg-stone-100 dark:bg-darkcard text-stone-400">
                <i class="ph-bold ph-whatsapp-logo text-xs"></i>
            </button>
        `;

        // Multi-user ownership & permissions
        const currentUser = appState.currentUser || {};
        const currentAssigned = (lead.assigned_to || '').trim();
        const isUnassigned = !currentAssigned || currentAssigned.toLowerCase() === 'unassigned' || currentAssigned === 'Sem Atribuição';
        const isOwner = Boolean(currentUser.name && currentAssigned.toLowerCase() === currentUser.name.toLowerCase());
        const isAdmin = (currentUser.permission_level === 'ADMIN');
        const canEdit = isOwner || isAdmin || isUnassigned;

        // Operator Column UI
        let operatorCellHtml = '';
        if (isUnassigned) {
            operatorCellHtml = `
                <button onclick="claimLead(${lead.id})" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 hover:bg-stone-800 dark:hover:bg-white transition shadow-xs" title="Puxar lead para você com 1 clique">
                    <i class="ph-bold ph-hand-pointing text-xs"></i>
                    <span>Assumir Lead</span>
                </button>
            `;
        } else if (isAdmin) {
            const operatorOptions = appState.operators.length > 0 ? appState.operators.map(op => {
                return `<option value="${escapeHtml(op.name)}" ${op.name === currentAssigned ? 'selected' : ''}>${escapeHtml(op.name)}</option>`;
            }).join('') : `<option value="${escapeHtml(currentAssigned)}" selected>${escapeHtml(currentAssigned)}</option>`;

            operatorCellHtml = `
                <select onchange="changeLeadOperator(${lead.id}, this.value)" class="px-2 py-1 rounded-md text-[11px] font-medium border border-stone-200 dark:border-darkborder bg-white dark:bg-darkcard text-stone-700 dark:text-stone-200 focus:outline-none focus:border-stone-500 cursor-pointer" title="Gerente: Reatribuir vendedor">
                    ${operatorOptions}
                </select>
            `;
        } else if (isOwner) {
            operatorCellHtml = `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900/40" title="Você é o responsável por este lead">
                    <i class="ph-bold ph-check-circle text-emerald-600"></i> Seu Lead
                </span>
            `;
        } else {
            operatorCellHtml = `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-stone-100 text-stone-600 dark:bg-darkcard2 dark:text-stone-300 border border-stone-200 dark:border-darkborder" title="Lead sob responsabilidade de ${escapeHtml(currentAssigned)}">
                    <i class="ph-bold ph-lock text-stone-400"></i> ${escapeHtml(currentAssigned)}
                </span>
            `;
        }

        // Status & CRM Column UI
        let statusCellHtml = '';
        if (canEdit) {
            statusCellHtml = `
                <select onchange="changeLeadCrmStatus(${lead.id}, this.value)" class="px-2 py-1 rounded-md text-[11px] font-medium border border-stone-200 dark:border-darkborder bg-white dark:bg-darkcard text-stone-700 dark:text-stone-200 focus:outline-none focus:border-stone-500 cursor-pointer">
                    <option value="Novo" ${lead.crm_status === 'Novo' ? 'selected' : ''}>Novo</option>
                    <option value="Contatado" ${lead.crm_status === 'Contatado' ? 'selected' : ''}>Contatado</option>
                    <option value="Reunião Agendada" ${lead.crm_status === 'Reunião Agendada' ? 'selected' : ''}>Reunião Agendada</option>
                    <option value="Em Negociação" ${lead.crm_status === 'Em Negociação' ? 'selected' : ''}>Em Negociação</option>
                    <option value="Fechado (R$ 1.000)" ${lead.crm_status === 'Fechado (R$ 1.000)' ? 'selected' : ''}>Fechado (R$ 1.000)</option>
                    <option value="Perdido" ${lead.crm_status === 'Perdido' ? 'selected' : ''}>Perdido</option>
                </select>
                ${scheduleBadge}
            `;
        } else {
            statusCellHtml = `
                <div class="space-y-1">
                    <span class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-bold bg-stone-100 dark:bg-darkcard2 text-stone-600 dark:text-stone-300 border border-stone-200 dark:border-darkborder" title="Em atendimento por ${escapeHtml(currentAssigned)}">
                        <i class="ph-bold ph-lock text-stone-400"></i> ${escapeHtml(lead.crm_status || 'Novo')}
                    </span>
                    ${scheduleBadge}
                </div>
            `;
        }

        return `
            <tr class="border-b border-stone-200/60 dark:border-darkborder/50 hover:bg-[#F5F3EF]/60 dark:hover:bg-darkcard2/40 transition-colors">
                <!-- 1. Score -->
                <td class="py-2.5 px-3 whitespace-nowrap">
                    <div class="flex flex-col gap-0.5">
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold font-mono w-max ${scoreClass}">
                            ${lead.lead_score} pts
                        </span>
                        <span class="text-[9px] text-stone-400 font-medium">${priorityLabel}</span>
                    </div>
                </td>

                <!-- 2. Empresa & Local + Distância da Casa -->
                <td class="py-2.5 px-3 company-col-cell" style="${getCompanyColWidthStyle()}">
                    <div class="font-bold text-stone-900 dark:text-white leading-tight break-words text-xs whitespace-normal">
                        ${escapeHtml(lead.name)}
                    </div>
                    <div class="text-[10px] text-stone-500 dark:text-stone-400 break-words flex items-start gap-1 mt-0.5 leading-snug whitespace-normal">
                        <i class="ph ph-map-pin text-[11px] shrink-0 mt-0.5 text-stone-400"></i>
                        <span>${escapeHtml(lead.address || 'Brasil')}</span>
                    </div>
                    ${lead.distance_km != null ? `
                        <div class="mt-1 inline-flex items-center gap-1 text-[9.5px] font-medium text-stone-600 dark:text-stone-300 bg-stone-100 dark:bg-stone-800/80 px-1.5 py-0.5 rounded border border-stone-200 dark:border-stone-700" title="Distância estimada da sua residência (R. Lótus, 450 - Araucária/PR)">
                            <i class="ph-bold ph-navigation-arrow text-[9px]"></i>
                            <span>${lead.distance_km.toFixed(1)} km de você</span>
                        </div>
                    ` : ''}

                    <!-- CNPJ Status & Sócios Badge -->
                    <div class="mt-1 flex items-center gap-1 flex-wrap">
                        ${lead.cnpj && lead.cnpj !== 'Não localizado' ? `
                            <button type="button" onclick="openCnpjModal(${lead.id})" class="inline-flex items-center gap-1 text-[9.5px] font-medium px-1.5 py-0.5 rounded border transition cursor-pointer ${
                                lead.cnpj_situacao === 'ATIVA' 
                                    ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/60 hover:border-emerald-400' 
                                    : 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800/60 hover:border-rose-400'
                            }" title="${lead.cnpj_situacao === 'ATIVA' ? 'CNPJ Ativo na Receita Federal • Clique para ver sócios' : 'CNPJ Inativo/Baixado na Receita Federal'}">
                                <i class="ph-bold ${lead.cnpj_situacao === 'ATIVA' ? 'ph-identification-card text-emerald-600' : 'ph-warning-octagon text-rose-600'} text-[10px]"></i>
                                <span>${escapeHtml(lead.cnpj)} (${escapeHtml(lead.cnpj_situacao || 'ATIVA')})</span>
                            </button>
                        ` : (lead.cnpj_situacao === 'NÃO LOCALIZADO' ? `
                            <button type="button" onclick="fetchLeadCnpj(${lead.id}, true)" id="btnCnpj_${lead.id}" class="inline-flex items-center gap-1 text-[9.5px] text-stone-400 dark:text-stone-500 bg-stone-50 dark:bg-darkcard px-1.5 py-0.5 rounded border border-dashed border-stone-200 dark:border-darkborder hover:text-stone-700 dark:hover:text-stone-200 transition cursor-pointer" title="CNPJ não localizado automaticamente • Clique para tentar nova busca">
                                <i class="ph-bold ph-question text-[10px]"></i>
                                <span>Sem CNPJ (Tentar busca)</span>
                            </button>
                        ` : `
                            <button type="button" onclick="fetchLeadCnpj(${lead.id})" id="btnCnpj_${lead.id}" class="inline-flex items-center gap-1 text-[9.5px] font-medium text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white bg-stone-100 hover:bg-stone-200 dark:bg-darkcard2 dark:hover:bg-darkcard px-1.5 py-0.5 rounded border border-stone-200 dark:border-darkborder transition cursor-pointer" title="Buscar CNPJ, Situação Cadastral e Sócios na Receita Federal">
                                <i class="ph-bold ph-identification-card text-[10px]"></i>
                                <span>Buscar CNPJ</span>
                            </button>
                        `)}
                    </div>
                </td>

                <!-- 3. Contato + Phone Type Badge -->
                <td class="py-2.5 px-3 whitespace-nowrap font-mono text-[11px]">
                    <div class="space-y-0.5">
                        <div class="flex items-center gap-1 text-stone-700 dark:text-stone-200 font-medium">
                            <i class="ph ph-phone text-stone-400 text-xs"></i>
                            <span>${lead.phone || '<span class="text-stone-400 font-sans text-[10px]">Sem telefone</span>'}</span>
                        </div>
                        <div>${phoneTypeBadge}</div>
                    </div>
                </td>

                <!-- 4. Google Maps Stats -->
                <td class="py-2.5 px-3 whitespace-nowrap">
                    <div class="flex items-center gap-1 text-stone-800 dark:text-stone-200 font-bold text-xs">
                        <i class="ph-fill ph-star text-amber-500 text-xs"></i>
                        <span>${lead.rating ? lead.rating.toFixed(1) : '0.0'}</span>
                        <span class="text-stone-400 text-[10px] font-normal">(${lead.reviews_count || 0})</span>
                    </div>
                </td>

                <!-- 5. Diagnóstico Web & Print Proof -->
                <td class="py-2.5 px-3 min-w-[170px] max-w-[240px]">
                    <div class="space-y-1">
                        <div class="flex items-center gap-1 flex-wrap">
                            ${qualBadge}
                            ${lead.website ? `
                                <button onclick="openScreenshotModal(${lead.id})" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-stone-100 hover:bg-stone-900 hover:text-white dark:bg-darkborder dark:hover:bg-white dark:hover:text-stone-900 text-stone-700 dark:text-stone-300 border border-stone-200 dark:border-darkborder transition cursor-pointer" title="Ver print do site capturado">
                                    <i class="ph-bold ph-camera text-[10px]"></i>
                                    <span>Print</span>
                                </button>
                            ` : `
                                <button onclick="openScreenshotModal(${lead.id})" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#FFF7ED] hover:bg-stone-900 hover:text-white text-[#9A3412] border border-[#FFEDD5] transition cursor-pointer" title="Ver diagnóstico visual de ausência de site">
                                    <i class="ph-bold ph-camera-slash text-[10px]"></i>
                                    <span>Sem Site</span>
                                </button>
                            `}
                        </div>
                        <div class="text-[9.5px] text-stone-400 break-words leading-tight" title="${escapeHtml(lead.qualification_detail || '')}">
                            ${escapeHtml(lead.qualification_detail || 'Sem site')}
                        </div>
                    </div>
                </td>

                <!-- 6. SDR Responsável -->
                <td class="py-2.5 px-3 whitespace-nowrap">
                    ${operatorCellHtml}
                </td>

                <!-- 7. Status & Agenda -->
                <td class="py-2.5 px-3 whitespace-nowrap">
                    ${statusCellHtml}
                </td>

                <!-- 8. Ações Comerciais -->
                <td class="py-2.5 px-3 whitespace-nowrap text-center">
                    <div class="flex items-center justify-center gap-1">
                        <!-- Script Button -->
                        <button onclick="openScriptModal(${lead.id})" class="px-2 py-1 rounded-md text-[11px] font-semibold bg-stone-100 dark:bg-darkborder text-stone-700 dark:text-stone-200 hover:bg-stone-900 hover:text-white dark:hover:bg-white dark:hover:text-stone-900 transition border border-stone-200 dark:border-darkborder flex items-center gap-1" title="Ver roteiro comercial">
                            <i class="ph-bold ph-phone-call text-xs"></i>
                            <span>Script</span>
                        </button>

                        <!-- Notes Button -->
                        <button onclick="openNotesModal(${lead.id}, '${escapeHtml(lead.name)}')" class="px-2 py-1 rounded-md text-[11px] font-semibold bg-stone-100 dark:bg-darkborder text-stone-700 dark:text-stone-200 hover:bg-stone-900 hover:text-white dark:hover:bg-white dark:hover:text-stone-900 transition border border-stone-200 dark:border-darkborder flex items-center gap-0.5" title="Anotações e Histórico de Ligações">
                            <i class="ph-bold ph-note-pencil text-xs"></i>
                            <span>Notas</span>
                            ${notesBadge}
                        </button>

                        <!-- Proposal PDF Button -->
                        <button onclick="openProposalModal(${lead.id})" class="p-1.5 rounded-md text-stone-600 dark:text-stone-300 hover:bg-stone-900 hover:text-white dark:hover:bg-white dark:hover:text-stone-900 border border-stone-200 dark:border-darkborder transition" title="Gerar Proposta Comercial PDF">
                            <i class="ph-bold ph-file-pdf text-xs"></i>
                        </button>

                        <!-- Schedule Call Button -->
                        <button onclick="openScheduleModal(${lead.id}, '${escapeHtml(lead.name)}')" class="p-1.5 rounded-md text-stone-600 dark:text-stone-300 hover:bg-stone-900 hover:text-white dark:hover:bg-white dark:hover:text-stone-900 border border-stone-200 dark:border-darkborder transition" title="Agendar Reunião ou Call com o lead">
                            <i class="ph-bold ph-calendar-plus text-xs"></i>
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
// 12. AGENDA DE REUNIÕES (CARDS & MANAGEMENT)
// ----------------------------------------------------
async function loadAgendaMeetings() {
    try {
        const res = await fetch('/api/meetings');
        const data = await res.json();
        if (!data.success) return;

        const meetings = data.meetings || [];
        const count = meetings.length;

        // Update counters
        const sideCount = document.getElementById('sideAgendaCount');
        if (sideCount) sideCount.innerText = count;

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
                <div class="glass-panel p-4 rounded-xl space-y-2.5 relative overflow-hidden border-l-4 border-l-stone-800 dark:border-l-stone-200">
                    <div class="flex items-start justify-between">
                        <div>
                            <span class="text-[9px] font-bold uppercase tracking-wider text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-darkborder px-1.5 py-0.5 rounded">
                                Reunião Marcada
                            </span>
                            <h4 class="font-bold text-xs text-stone-900 dark:text-white mt-1 break-words">${escapeHtml(m.name)}</h4>
                            <p class="text-[11px] text-stone-400 font-mono">${m.phone || 'Sem telefone'}</p>
                            <span class="text-[9.5px] text-stone-400 block mt-0.5">SDR: <strong>${escapeHtml(m.assigned_to || 'Jamilly')}</strong></span>
                        </div>
                        <div class="text-right">
                            <span class="text-[11px] font-bold text-stone-900 dark:text-white block font-mono">${escapeHtml(m.scheduled_at)}</span>
                            <span class="text-[9.5px] text-stone-400 break-words">${escapeHtml(m.address || 'Brasil')}</span>
                        </div>
                    </div>

                    ${m.meeting_notes ? `
                        <div class="text-[11px] p-2 rounded-lg bg-stone-50 dark:bg-darkcard text-stone-600 dark:text-stone-300 border border-stone-100 dark:border-darkborder/50">
                            <strong>Pauta:</strong> ${escapeHtml(m.meeting_notes)}
                        </div>
                    ` : ''}

                    <div class="pt-2 flex flex-wrap items-center justify-between gap-2 border-t border-stone-100 dark:border-darkborder/50">
                        <!-- Status Changer -->
                        <div class="flex items-center gap-1">
                            <select onchange="handleAgendaStatusChange(${m.id}, this.value)" class="px-2 py-1 rounded-md text-[10.5px] font-medium border border-stone-200 dark:border-darkborder bg-white dark:bg-darkcard text-stone-700 dark:text-stone-200 cursor-pointer">
                                <option value="Reunião Agendada" selected>Status: Agendada</option>
                                <option value="Fechado (R$ 1.000)">Fechado (R$ 1.000)</option>
                                <option value="Em Negociação">Em Negociação</option>
                                <option value="Perdido">Perdido (Remover)</option>
                                <option value="Cancelar Reunião">Cancelar Reunião</option>
                            </select>
                        </div>

                        <div class="flex items-center gap-1">
                            <!-- Button: Notes -->
                            <button onclick="openNotesModal(${m.id}, '${escapeHtml(m.name)}')" class="px-2 py-1 rounded-md text-[10.5px] font-medium text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-darkborder hover:bg-stone-200 transition" title="Anotações da Call">
                                <i class="ph-bold ph-note-pencil"></i>
                                <span>Notas</span>
                            </button>

                            <!-- Button: Remove / Unschedule Meeting -->
                            <button onclick="unscheduleMeeting(${m.id})" class="px-2 py-1 rounded-md text-[10.5px] font-medium text-stone-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20 transition" title="Remover da Agenda">
                                <i class="ph-bold ph-calendar-x"></i>
                                <span>Remover</span>
                            </button>
                            
                            <!-- Button: WhatsApp Direct -->
                            ${m.whatsapp_url ? `
                                <a href="${m.whatsapp_url}" target="_blank" class="px-2.5 py-1 rounded-md text-[10.5px] font-bold bg-[#15803D] text-white hover:bg-[#166534] flex items-center gap-1 transition shadow-sm">
                                    <i class="ph-bold ph-whatsapp-logo"></i>
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
            loadTodaysMeetings();
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
            loadTodaysMeetings();
            loadKpis();
        } else {
            showToast('Erro ao remover reunião.', 'error');
        }
    } catch (err) {
        showToast('Erro ao remover reunião: ' + err.message, 'error');
    }
}

// ----------------------------------------------------
// 13. INTERACTION NOTES & CRM TIMELINE
// ----------------------------------------------------
async function openNotesModal(leadId, leadName) {
    appState.activeNotesLeadId = leadId;
    const nameEl = document.getElementById('notesModalCompanyName');
    if (nameEl) nameEl.innerText = leadName;

    const input = document.getElementById('newNoteInput');
    if (input) input.value = '';

    const container = document.getElementById('notesListContainer');
    if (container) container.innerHTML = `<div class="text-center py-6 text-slate-400 text-xs">Carregando anotações...</div>`;

    document.getElementById('notesModal').classList.remove('hidden');

    try {
        const res = await fetch(`/api/lead/${leadId}/notes`);
        const data = await res.json();
        if (data.success) {
            renderNotesList(data.notes || []);
        }
    } catch (err) {
        if (container) container.innerHTML = `<div class="text-center text-rose-500 text-xs">Erro ao carregar histórico.</div>`;
    }
}

function closeNotesModal() {
    document.getElementById('notesModal').classList.add('hidden');
    appState.activeNotesLeadId = null;
}

function renderNotesList(notes) {
    const container = document.getElementById('notesListContainer');
    if (!container) return;

    if (!notes || notes.length === 0) {
        container.innerHTML = `
            <div class="py-8 text-center text-slate-400 text-xs space-y-1">
                <i class="ph ph-note text-2xl"></i>
                <p>Nenhuma anotação registrada ainda.</p>
                <p class="text-[10px]">Registre o que o cliente disse na ligação ou no WhatsApp.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = notes.map(n => {
        return `
            <div class="p-3 rounded-xl bg-slate-50 dark:bg-darkcard2 border border-slate-100 dark:border-darkborder space-y-1">
                <div class="flex items-center justify-between text-[10px] text-slate-400">
                    <span class="font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        <i class="ph-bold ph-user text-brand-500"></i> ${escapeHtml(n.operator_name || 'Jamilly')}
                    </span>
                    <span>${escapeHtml(n.created_at || '')}</span>
                </div>
                <p class="text-xs text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
                    ${escapeHtml(n.note_text)}
                </p>
            </div>
        `;
    }).join('');
}

async function saveNewNote() {
    if (!appState.activeNotesLeadId) return;

    const input = document.getElementById('newNoteInput');
    const text = input ? input.value.trim() : '';

    if (!text) {
        showToast('Digite uma anotação antes de salvar.', 'error');
        return;
    }

    try {
        const res = await fetch(`/api/lead/${appState.activeNotesLeadId}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                note_text: text,
                operator: appState.activeOperator || 'Jamilly'
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Anotação registrada com sucesso!', 'success');
            if (input) input.value = '';

            // Refresh notes list
            const resNotes = await fetch(`/api/lead/${appState.activeNotesLeadId}/notes`);
            const dataNotes = await resNotes.json();
            if (dataNotes.success) {
                renderNotesList(dataNotes.notes || []);
            }
            loadLeadsTable();
        } else {
            showToast(data.error || 'Erro ao salvar anotação.', 'error');
        }
    } catch (err) {
        showToast('Erro de comunicação: ' + err.message, 'error');
    }
}

// ----------------------------------------------------
// 14. 1-CLICK COMMERCIAL PROPOSAL IN PDF & TEXT
// ----------------------------------------------------
async function openProposalModal(leadId) {
    try {
        const res = await fetch(`/api/lead/${leadId}/script`);
        const data = await res.json();
        if (!data.success) {
            showToast('Erro ao carregar dados da proposta.', 'error');
            return;
        }

        const lead = data.lead;
        appState.activeProposalLead = lead;
        appState.activeLeadData = data;

        document.getElementById('proposalModalCompanyName').innerText = lead.name;
        document.getElementById('proposalModalOperator').innerText = lead.assigned_to || appState.activeOperator || 'Jamilly';

        const printLink = document.getElementById('proposalPrintLink');
        if (printLink) {
            printLink.href = `/lead/${leadId}/proposal_print`;
        }

        document.getElementById('proposalModal').classList.remove('hidden');
    } catch (err) {
        showToast('Erro ao abrir proposta: ' + err.message, 'error');
    }
}

function closeProposalModal() {
    document.getElementById('proposalModal').classList.add('hidden');
    appState.activeProposalLead = null;
}

function copyProposalTextFromModal() {
    if (!appState.activeLeadData || !appState.activeLeadData.proposal_text) {
        showToast('Texto da proposta indisponível.', 'error');
        return;
    }

    navigator.clipboard.writeText(appState.activeLeadData.proposal_text).then(() => {
        showToast('Proposta completa copiada para a área de transferência!', 'success');
    }).catch(() => {
        showToast('Não foi possível copiar.', 'error');
    });
}

// ----------------------------------------------------
// 15. SCRIPT MODAL (COLD CALL + WHATSAPP CADENCE)
// ----------------------------------------------------
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
        let coldCall = data.cold_call_script;
        if (lead.cnpj_socios && lead.cnpj_socios !== 'Proprietário não identificado') {
            const firstSocio = lead.cnpj_socios.split(',')[0].trim();
            coldCall = `★ GANCHO DE FECHAMENTO (SÓCIO NA RECEITA FEDERAL):\n"Olá! Gostaria de falar com ${firstSocio}, por favor? Sou ${lead.assigned_to || appState.activeOperator || 'Jamilly'} da Marq Lab..."\n\n----------------------------------------\n` + coldCall;
        }

        if (lead.cnpj_situacao && lead.cnpj_situacao !== 'ATIVA' && lead.cnpj && lead.cnpj !== 'Não localizado') {
            coldCall = `[ALERTA CADASTRAL] CNPJ ${lead.cnpj_situacao} NA RECEITA FEDERAL (${escapeHtml(lead.cnpj)})\nEsta empresa consta como ${lead.cnpj_situacao} nos registros oficiais (pode ser baixa voluntária ou encerramento de atividades). Tenha cautela na abordagem ou utilize como gancho de regularização comercial.\n\n----------------------------------------\n` + coldCall;
        }

        if (lead.cnpj && lead.cnpj !== 'Não localizado') {
            document.getElementById('modalSubtitle').innerText = `${lead.qualification_status} • CNPJ: ${lead.cnpj} (${lead.cnpj_situacao || 'ATIVA'}) • SDR: ${lead.assigned_to || 'Jamilly'}`;
        } else {
            document.getElementById('modalSubtitle').innerText = `${lead.qualification_status} • Score: ${lead.lead_score} pts • ${lead.phone || 'Sem telefone'} • SDR: ${lead.assigned_to || 'Jamilly'}`;
        }

        document.getElementById('modalColdCallText').value = coldCall;
        document.getElementById('modalWhatsAppText').value = data.whatsapp_script;
        document.getElementById('modalFollowup1Text').value = data.whatsapp_followup_1 || '';
        document.getElementById('modalFollowup2Text').value = data.whatsapp_followup_2 || '';
        document.getElementById('modalProposalPlainText').value = data.proposal_text || '';

        // WhatsApp links
        const wpLink = document.getElementById('modalWhatsAppLink');
        if (data.whatsapp_url) {
            wpLink.href = data.whatsapp_url;
            wpLink.classList.remove('hidden');
        } else {
            wpLink.classList.add('hidden');
        }

        const fu1Link = document.getElementById('modalFollowup1Link');
        if (fu1Link) {
            if (data.followup_1_url) {
                fu1Link.href = data.followup_1_url;
                fu1Link.classList.remove('hidden');
            } else {
                fu1Link.classList.add('hidden');
            }
        }

        const fu2Link = document.getElementById('modalFollowup2Link');
        if (fu2Link) {
            if (data.followup_2_url) {
                fu2Link.href = data.followup_2_url;
                fu2Link.classList.remove('hidden');
            } else {
                fu2Link.classList.add('hidden');
            }
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
    const tabs = ['coldcall', 'whatsapp', 'followup1', 'followup2', 'proposalText'];
    const tabBtns = {
        coldcall: document.getElementById('tabColdCallBtn'),
        whatsapp: document.getElementById('tabWhatsAppBtn'),
        followup1: document.getElementById('tabFollowup1Btn'),
        followup2: document.getElementById('tabFollowup2Btn'),
        proposalText: document.getElementById('tabProposalTextBtn'),
    };
    const tabContents = {
        coldcall: document.getElementById('modalColdCallContent'),
        whatsapp: document.getElementById('modalWhatsAppContent'),
        followup1: document.getElementById('modalFollowup1Content'),
        followup2: document.getElementById('modalFollowup2Content'),
        proposalText: document.getElementById('modalProposalTextContent'),
    };

    tabs.forEach(t => {
        const btn = tabBtns[t];
        const content = tabContents[t];
        if (!btn || !content) return;

        if (t === tab) {
            btn.className = 'pb-2 border-b-2 border-brand-500 text-brand-600 dark:text-brand-400 flex items-center gap-1.5 px-2';
            content.classList.remove('hidden');
        } else {
            btn.className = 'pb-2 border-b-2 border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-white flex items-center gap-1.5 px-2';
            content.classList.add('hidden');
        }
    });
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
// 16. CRM STATUS & CLEAR DATABASE
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
        } else {
            showToast(data.error || 'Erro ao atualizar status.', 'error');
            loadLeadsTable();
        }
    } catch (err) {
        showToast('Erro ao atualizar status: ' + err.message, 'error');
        loadLeadsTable();
    }
}

function confirmClearLeads() {
    const isAdmin = appState.currentUser && appState.currentUser.permission_level === 'ADMIN';
    if (!isAdmin) {
        showToast('Acesso Restrito: Apenas Gestores/Administradores podem limpar a base de leads.', 'error');
        return;
    }
    document.getElementById('clearConfirmModal').classList.remove('hidden');
}

function closeClearModal() {
    document.getElementById('clearConfirmModal').classList.add('hidden');
}

async function executeClearLeads() {
    try {
        const res = await fetch('/api/leads/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operator: appState.activeOperator })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Base de leads e histórico limpos com sucesso!', 'success');
            closeClearModal();
            loadDashboardData();
        } else {
            showToast(data.error || 'Erro ao limpar base.', 'error');
        }
    } catch (err) {
        showToast('Erro de comunicação: ' + err.message, 'error');
    }
}

// ----------------------------------------------------
// 16. WEBSITE SCREENSHOT VIEWER (WARM MINIMALIST & FAST WORKER)
// ----------------------------------------------------
let currentScreenshotLeadId = null;

async function openScreenshotModal(leadId, refresh = false) {
    currentScreenshotLeadId = leadId;

    const modal = document.getElementById('screenshotModal');
    const titleEl = document.getElementById('screenshotModalTitle');
    const urlEl = document.getElementById('screenshotModalUrl');
    const container = document.getElementById('screenshotContainer');
    const directLink = document.getElementById('screenshotDirectLink');
    const auditNotes = document.getElementById('screenshotAuditNotes');

    const lead = appState.currentLeads.find(l => l.id == leadId);
    const leadName = lead ? lead.name : 'Empresa';
    const websiteUrl = lead ? (lead.website || '') : '';
    const auditDetail = lead ? (lead.qualification_detail || '') : '';

    if (titleEl) titleEl.innerText = `Print: ${leadName}`;
    if (urlEl) urlEl.innerText = websiteUrl || 'Sem website cadastrado no Google Maps';
    if (directLink) {
        if (websiteUrl) {
            directLink.href = websiteUrl.startsWith('http') ? websiteUrl : `http://${websiteUrl}`;
            directLink.classList.remove('hidden');
        } else {
            directLink.classList.add('hidden');
        }
    }
    if (auditNotes) {
        auditNotes.innerHTML = `
            <i class="ph-bold ph-info text-stone-500 text-xs"></i>
            <span><strong>Diagnóstico:</strong> ${escapeHtml(auditDetail || (websiteUrl ? 'Necessita modernização de design e botão de WhatsApp.' : 'Empresa sem website cadastrado - Alvo de alta prioridade.'))}</span>
        `;
    }

    // Immediately clear previous lead's image and show clean loader
    if (container) {
        container.innerHTML = `
            <div class="py-16 text-center text-stone-500 space-y-3">
                <div class="inline-block w-6 h-6 border-2 border-stone-800 dark:border-stone-200 border-t-transparent rounded-full animate-spin"></div>
                <p class="text-xs font-semibold text-stone-800 dark:text-stone-200">Renderizando visualização...</p>
                <p class="text-[11px] text-stone-400">Playwright capturando em alta velocidade.</p>
            </div>
        `;
    }

    if (modal) modal.classList.remove('hidden');

    try {
        const urlToFetch = refresh ? `/api/lead/${leadId}/screenshot?refresh=1` : `/api/lead/${leadId}/screenshot`;
        const res = await fetch(urlToFetch);
        const data = await res.json();

        // If the user navigated to another lead while waiting, do not render this stale response
        if (currentScreenshotLeadId !== leadId) {
            return;
        }

        if (data.lead_name && titleEl) titleEl.innerText = `Print: ${data.lead_name}`;
        if (data.website && urlEl) urlEl.innerText = data.website;

        if (data.success && data.screenshot_url) {
            const timeLabel = data.cached_at || 'agora';
            container.innerHTML = `
                <div class="w-full flex flex-col items-center gap-2">
                    <img src="${data.screenshot_url}?t=${Date.now()}" alt="Screenshot de ${escapeHtml(data.lead_name || leadName)}"
                        class="w-full max-h-[68vh] object-contain object-top rounded-lg border border-stone-200 dark:border-darkborder bg-white shadow-sm">
                    <div class="text-[10px] text-stone-500 flex items-center justify-between w-full px-1 pt-1 font-mono">
                        <span class="flex items-center gap-1.5 text-stone-600 dark:text-stone-300">
                            <i class="ph-bold ph-check text-emerald-600"></i>
                            <span>Capturado em ${escapeHtml(timeLabel)}</span>
                        </span>
                        <button onclick="openScreenshotModal(${leadId}, true)" class="text-[10px] text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:white underline flex items-center gap-1 cursor-pointer">
                            <i class="ph-bold ph-arrows-clockwise"></i> Recarregar Print
                        </button>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="py-12 text-center text-stone-600 dark:text-stone-300 space-y-2">
                    <i class="ph-bold ph-warning-circle text-2xl text-amber-600"></i>
                    <p class="text-xs font-semibold">${escapeHtml(data.error || 'Não foi possível capturar o print deste site.')}</p>
                    <p class="text-[11px] text-stone-400">O servidor pode estar offline, bloqueando automações ou sem SSL.</p>
                    <button onclick="openScreenshotModal(${leadId}, true)" class="mt-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 hover:bg-stone-800 transition cursor-pointer">
                        Tentar Novamente
                    </button>
                </div>
            `;
        }
    } catch (err) {
        if (currentScreenshotLeadId !== leadId) return;
        container.innerHTML = `
            <div class="py-12 text-center text-stone-600 dark:text-stone-300 space-y-2">
                <i class="ph-bold ph-x-circle text-2xl text-rose-600"></i>
                <p class="text-xs font-semibold">Falha de conexão com o servidor.</p>
                <p class="text-[11px] text-stone-400">${escapeHtml(err.message)}</p>
                <button onclick="openScreenshotModal(${leadId}, true)" class="mt-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 hover:bg-stone-800 transition cursor-pointer">
                    Tentar Novamente
                </button>
            </div>
        `;
    }
}

function closeScreenshotModal() {
    currentScreenshotLeadId = null;
    const modal = document.getElementById('screenshotModal');
    if (modal) modal.classList.add('hidden');
    const container = document.getElementById('screenshotContainer');
    if (container) container.innerHTML = '';
}

// ----------------------------------------------------
// 17. TOAST NOTIFICATIONS & UTILITIES
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

// ----------------------------------------------------
// 18. CNPJ DISCOVERY & RECEITA FEDERAL ENRICHMENT
// ----------------------------------------------------
appState.activeCnpjLeadId = null;

async function fetchLeadCnpj(leadId, force = false) {
    const btn = document.getElementById(`btnCnpj_${leadId}`);
    if (btn) {
        btn.innerHTML = `<div class="inline-block w-2.5 h-2.5 border border-stone-800 dark:border-stone-200 border-t-transparent rounded-full animate-spin"></div> <span>Buscando...</span>`;
        btn.disabled = true;
    }

    try {
        const res = await fetch(`/api/lead/${leadId}/cnpj${force ? '?refresh=1' : ''}`, {
            method: 'POST'
        });
        const data = await res.json();
        if (data.success && data.data && data.data.cnpj && data.data.cnpj !== 'Não localizado') {
            showToast(`CNPJ ${data.data.cnpj_formatted} identificado com sucesso!`, 'success');
            const lead = appState.currentLeads.find(l => l.id == leadId);
            if (lead) {
                lead.cnpj = data.data.cnpj_formatted;
                lead.cnpj_razao_social = data.data.razao_social;
                lead.cnpj_situacao = data.data.situacao_cadastral;
                lead.cnpj_porte = data.data.porte;
                lead.cnpj_socios = data.data.socios_str;
                lead.cnpj_abertura = data.data.data_inicio_atividade;
                lead.cnpj_capital = data.data.capital_social;
                lead.cnpj_cnae = data.data.cnae_fiscal_descricao;
                lead.cnpj_regime = data.data.regime;
            }
            loadLeadsTable();
            openCnpjModal(leadId);
        } else {
            showToast('CNPJ não localizado automaticamente nos registros públicos.', 'info');
            const lead = appState.currentLeads.find(l => l.id == leadId);
            if (lead) {
                lead.cnpj_situacao = 'NÃO LOCALIZADO';
            }
            loadLeadsTable();
        }
    } catch (err) {
        showToast('Erro ao consultar CNPJ: ' + err.message, 'error');
        if (btn) {
            btn.innerHTML = `<i class="ph-bold ph-identification-card text-[10px]"></i> <span>Buscar CNPJ</span>`;
            btn.disabled = false;
        }
    }
}

async function openCnpjModal(leadId) {
    appState.activeCnpjLeadId = leadId;
    const modal = document.getElementById('cnpjModal');
    const titleEl = document.getElementById('cnpjModalTitle');
    const subEl = document.getElementById('cnpjModalSubtitle');
    const container = document.getElementById('cnpjModalContent');

    const lead = appState.currentLeads.find(l => l.id == leadId);
    if (!lead) return;

    if (titleEl) titleEl.innerText = `Raio-X: ${lead.name}`;
    if (subEl) subEl.innerText = lead.cnpj_razao_social || 'Consulta Receita Federal';

    if (modal) modal.classList.remove('hidden');

    const situacao = lead.cnpj_situacao || 'ATIVA';
    const isAtiva = situacao === 'ATIVA';
    const sociosList = (lead.cnpj_socios || '').split(',').map(s => s.trim()).filter(Boolean);

    container.innerHTML = `
        <div class="p-3.5 rounded-lg border ${isAtiva ? 'bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/50' : 'bg-rose-50/60 dark:bg-rose-950/20 border-rose-200 dark:border-rose-800/50'} flex items-start justify-between gap-3">
            <div>
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${isAtiva ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'}">
                    <i class="ph-bold ${isAtiva ? 'ph-check-circle' : 'ph-x-circle'}"></i>
                    <span>SITUAÇÃO: ${situacao}</span>
                </span>
                <h3 class="mt-1.5 font-bold text-sm text-stone-900 dark:text-white font-mono">${escapeHtml(lead.cnpj || 'Não identificado')}</h3>
                <p class="text-[11px] text-stone-600 dark:text-stone-300 font-medium">${escapeHtml(lead.cnpj_razao_social || lead.name)}</p>
            </div>
            <button onclick="navigator.clipboard.writeText('${lead.cnpj || ''}'); showToast('CNPJ copiado!', 'success')" class="px-2 py-1 rounded text-xs font-medium border border-stone-200 dark:border-darkborder bg-white dark:bg-darkcard text-stone-700 dark:text-stone-200 hover:border-stone-400 transition flex items-center gap-1 shadow-xs shrink-0">
                <i class="ph ph-copy"></i> Copiar
            </button>
        </div>

        <div class="grid grid-cols-2 gap-2.5">
            <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200 dark:border-darkborder">
                <span class="text-[10px] uppercase font-bold text-stone-400">Tempo de Mercado / Abertura</span>
                <p class="text-xs font-semibold text-stone-800 dark:text-stone-200 mt-0.5 font-mono">${escapeHtml(lead.cnpj_abertura || 'Não informado')}</p>
            </div>
            <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200 dark:border-darkborder">
                <span class="text-[10px] uppercase font-bold text-stone-400">Porte & Regime</span>
                <p class="text-xs font-semibold text-stone-800 dark:text-stone-200 mt-0.5">${escapeHtml(lead.cnpj_porte || 'ME')} • ${escapeHtml(lead.cnpj_regime || 'Simples')}</p>
            </div>
        </div>

        <div class="p-3 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200 dark:border-darkborder space-y-1.5">
            <div class="flex items-center justify-between">
                <span class="text-[10px] uppercase font-bold text-stone-400 flex items-center gap-1">
                    <i class="ph-bold ph-users text-stone-600 dark:text-stone-300"></i>
                    <span>Sócios & Administradores Registrados (QSA)</span>
                </span>
                <span class="text-[10px] text-stone-400">${sociosList.length} pessoa(s)</span>
            </div>
            <div class="flex flex-wrap gap-1.5 pt-1">
                ${sociosList.length > 0 ? sociosList.map(socio => `
                    <span class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-white dark:bg-darkcard text-stone-800 dark:text-stone-200 border border-stone-200 dark:border-darkborder shadow-xs">
                        <i class="ph-bold ph-user-circle text-stone-500"></i>
                        <span>${escapeHtml(socio)}</span>
                    </span>
                `).join('') : `
                    <span class="text-xs text-stone-400 italic">Empresa individual ou sócio não listado na consulta rápida.</span>
                `}
            </div>
        </div>

        ${lead.cnpj_cnae ? `
            <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200 dark:border-darkborder">
                <span class="text-[10px] uppercase font-bold text-stone-400">Atividade Principal (CNAE)</span>
                <p class="text-xs text-stone-700 dark:text-stone-300 mt-0.5 leading-snug">${escapeHtml(lead.cnpj_cnae)}</p>
            </div>
        ` : ''}
    `;
}

function closeCnpjModal() {
    const modal = document.getElementById('cnpjModal');
    if (modal) modal.classList.add('hidden');
    appState.activeCnpjLeadId = null;
}

function openScriptFromCnpj() {
    const leadId = appState.activeCnpjLeadId;
    closeCnpjModal();
    if (leadId) {
        openScriptModal(leadId);
    }
}

async function enrichAllVisibleCnpjs() {
    const leadsToEnrich = (appState.currentLeads || []).filter(l => !l.cnpj || l.cnpj === 'Não localizado').slice(0, 8);
    if (leadsToEnrich.length === 0) {
        showToast('Todos os leads visíveis já possuem consulta de CNPJ.', 'info');
        return;
    }

    showToast(`Buscando CNPJ para ${leadsToEnrich.length} leads em segundo plano...`, 'info');
    for (const lead of leadsToEnrich) {
        await fetchLeadCnpj(lead.id, false);
        await new Promise(r => setTimeout(r, 1200));
    }
    showToast('Enriquecimento de CNPJs concluído!', 'success');
}

// ----------------------------------------------------
// 19. RADAR DE CNPJS RECÉM-ABERTOS CONTROLLER
// ----------------------------------------------------
appState.radarResults = [];

async function handleRadarCnpjScan(event) {
    if (event) event.preventDefault();

    const uf = (document.getElementById('radarUf')?.value || 'SP').trim();
    const cidade = (document.getElementById('radarCidade')?.value || 'Sorocaba').trim();
    const nicho = (document.getElementById('radarNicho')?.value || '').trim();
    const periodo = parseInt(document.getElementById('radarPeriodo')?.value || '60', 10);

    if (!cidade) {
        showToast('Informe a cidade para pesquisar.', 'error');
        return;
    }

    const btn = document.getElementById('btnRadarScan');
    const btnText = document.getElementById('btnRadarScanText');
    const container = document.getElementById('radarResultsContainer');

    if (btn) btn.disabled = true;
    if (btnText) {
        btnText.innerHTML = `
            <span class="inline-flex items-center gap-1.5">
                <div class="w-3 h-3 border-2 border-white dark:border-stone-900 border-t-transparent rounded-full animate-spin"></div>
                <span>Varrendo Receita Federal...</span>
            </span>
        `;
    }

    if (container) {
        container.innerHTML = `
            <div class="glass-panel p-10 text-center rounded-xl space-y-3 border border-amber-200/50 dark:border-amber-900/30">
                <div class="inline-block w-8 h-8 border-3 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
                <h4 class="font-bold text-xs text-stone-800 dark:text-stone-200 uppercase tracking-wider">
                    Varrendo Registros Públicos da Receita Federal
                </h4>
                <p class="text-[11px] text-stone-500 max-w-md mx-auto">
                    Identificando novas empresas abertas em <strong>${escapeHtml(cidade)}/${escapeHtml(uf)}</strong> nos últimos ${periodo} dias e extraindo quadro de sócios...
                </p>
            </div>
        `;
    }

    try {
        const res = await fetch('/api/radar_cnpj/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                uf,
                cidade,
                nicho,
                periodo_dias: periodo,
                limite: 20
            })
        });

        const data = await res.json();
        if (!data.success) {
            showToast(data.error || 'Erro ao escanear CNPJs.', 'error');
            if (container) {
                container.innerHTML = `
                    <div class="glass-panel p-8 text-center rounded-xl space-y-2 border border-dashed border-rose-300 dark:border-rose-900/50">
                        <i class="ph-bold ph-warning-octagon text-3xl text-rose-500"></i>
                        <h3 class="font-bold text-xs text-stone-800 dark:text-stone-200">Falha ao escanear empresas</h3>
                        <p class="text-[11px] text-stone-500 max-w-md mx-auto">${escapeHtml(data.error || 'Tente novamente em instantes.')}</p>
                    </div>
                `;
            }
            return;
        }

        appState.radarResults = data.empresas || [];
        renderRadarCnpjResults(data);
        showToast(`${appState.radarResults.length} empresas identificadas com sucesso!`, 'success');
    } catch (err) {
        showToast('Falha na comunicação: ' + err.message, 'error');
        if (container) {
            container.innerHTML = `
                <div class="glass-panel p-8 text-center rounded-xl space-y-2 border border-dashed border-rose-300 dark:border-rose-900/50">
                    <i class="ph-bold ph-x-circle text-3xl text-rose-500"></i>
                    <h3 class="font-bold text-xs text-stone-800 dark:text-stone-200">Erro de rede</h3>
                    <p class="text-[11px] text-stone-500">${escapeHtml(err.message)}</p>
                </div>
            `;
        }
    } finally {
        if (btn) btn.disabled = false;
        if (btnText) btnText.innerHTML = 'Escanear CNPJs';
    }
}

function renderRadarCnpjResults(data) {
    const container = document.getElementById('radarResultsContainer');
    if (!container) return;

    const empresas = data.empresas || [];
    if (empresas.length === 0) {
        container.innerHTML = `
            <div class="glass-panel p-8 text-center rounded-xl space-y-2 border border-dashed border-stone-300 dark:border-darkborder">
                <i class="ph-bold ph-magnifying-glass text-3xl text-stone-400"></i>
                <h3 class="font-bold text-xs text-stone-800 dark:text-stone-200">Nenhuma empresa recém-aberta encontrada</h3>
                <p class="text-[11px] text-stone-500 max-w-md mx-auto">
                    Não encontramos registros nos últimos ${data.parametros.periodo_dias} dias para estes filtros. Tente expandir para 90 ou 180 dias, ou pesquisar por outro ramo na cidade de ${escapeHtml(data.parametros.cidade)}.
                </p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="glass-panel p-4 rounded-xl flex flex-wrap items-center justify-between gap-3 border border-stone-200 dark:border-darkborder shadow-xs">
            <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span class="text-xs font-bold text-stone-900 dark:text-white">
                    ${empresas.length} empresa(s) recém-aberta(s) identificada(s)
                </span>
                <span class="text-[11px] text-stone-400">• ${escapeHtml(data.parametros.cidade)}/${escapeHtml(data.parametros.uf)}</span>
                ${data.parametros.nicho ? `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300">${escapeHtml(data.parametros.nicho)}</span>` : ''}
            </div>
            <div class="flex items-center gap-2">
                <button onclick="importAllRadarLeads()" id="btnImportAllRadar" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white dark:bg-white dark:text-stone-900 dark:hover:bg-stone-100 transition shadow-xs flex items-center gap-1.5 cursor-pointer">
                    <i class="ph-bold ph-download-simple"></i>
                    <span>Importar Todas (${empresas.length})</span>
                </button>
            </div>
        </div>

        <div class="grid grid-cols-1 gap-3">
            ${empresas.map((item, idx) => `
                <div class="glass-panel p-4 rounded-xl border border-stone-200 dark:border-darkborder space-y-3 hover:border-stone-400 transition" id="radarCard_${idx}">
                    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-2.5">
                        <div class="space-y-1">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 flex items-center gap-1 font-mono">
                                    <i class="ph-bold ph-calendar"></i>
                                    <span>${escapeHtml(item.tag_tempo)}</span>
                                </span>
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold ${item.situacao === 'ATIVA' ? 'bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300' : 'bg-rose-100 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300'} flex items-center gap-1 font-mono">
                                    <i class="ph-bold ${item.situacao === 'ATIVA' ? 'ph-check-circle' : 'ph-x-circle'}"></i>
                                    <span>${escapeHtml(item.situacao)}</span>
                                </span>
                                <span class="text-[11px] font-mono font-bold text-stone-500">${escapeHtml(item.cnpj)}</span>
                            </div>
                            <h3 class="font-bold text-sm text-stone-900 dark:text-white leading-snug">${escapeHtml(item.razao_social)}</h3>
                            ${item.nome_fantasia && item.nome_fantasia !== item.razao_social ? `<p class="text-xs text-stone-500 dark:text-stone-400 font-medium">Nome Fantasia: ${escapeHtml(item.nome_fantasia)}</p>` : ''}
                        </div>
                        <div class="flex items-center gap-1.5 shrink-0 self-start">
                            <span class="px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-stone-100 dark:bg-darkcard2 text-stone-800 dark:text-stone-200 border border-stone-200 dark:border-darkborder">
                                ${item.lead_score} pts
                            </span>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 pt-1 text-xs">
                        <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200/80 dark:border-darkborder/80 space-y-0.5">
                            <span class="text-[10px] uppercase font-bold text-stone-400 flex items-center gap-1">
                                <i class="ph-bold ph-users"></i> Sócios Registrados
                            </span>
                            <p class="font-medium text-stone-800 dark:text-stone-200 truncate" title="${escapeHtml(item.socios || 'Não informado')}">
                                ${escapeHtml(item.socios || 'Não informado / Individual')}
                            </p>
                        </div>

                        <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200/80 dark:border-darkborder/80 space-y-0.5">
                            <span class="text-[10px] uppercase font-bold text-stone-400 flex items-center gap-1">
                                <i class="ph-bold ph-briefcase"></i> Atividade / CNAE
                            </span>
                            <p class="font-medium text-stone-800 dark:text-stone-200 truncate" title="${escapeHtml(item.cnae || 'Serviços')}">
                                ${escapeHtml(item.cnae || 'Serviços')}
                            </p>
                        </div>

                        <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200/80 dark:border-darkborder/80 space-y-0.5">
                            <span class="text-[10px] uppercase font-bold text-stone-400 flex items-center gap-1">
                                <i class="ph-bold ph-map-pin"></i> Localização
                            </span>
                            <p class="font-medium text-stone-800 dark:text-stone-200 truncate" title="${escapeHtml(item.bairro ? `${item.bairro}, ${item.municipio}/${item.uf}` : `${item.municipio}/${item.uf}`)}">
                                ${escapeHtml(item.bairro ? `${item.bairro}, ${item.municipio}/${item.uf}` : `${item.municipio}/${item.uf}`)}
                            </p>
                        </div>

                        <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200/80 dark:border-darkborder/80 space-y-0.5">
                            <span class="text-[10px] uppercase font-bold text-stone-400 flex items-center gap-1">
                                <i class="ph-bold ph-phone"></i> Contato Telefônico
                            </span>
                            <p class="font-medium font-mono text-stone-800 dark:text-stone-200 truncate">
                                ${item.phone ? escapeHtml(item.phone) : '<span class="text-stone-400 italic font-sans">Sem telefone público</span>'}
                            </p>
                        </div>
                    </div>

                    <!-- Expandable Pitch Drawer -->
                    <div id="radarPitchDrawer_${idx}" class="hidden p-3.5 rounded-lg bg-[#F5F3EF] dark:bg-darkcard2 border border-stone-200 dark:border-darkborder space-y-3">
                        <div class="space-y-1">
                            <div class="flex items-center justify-between">
                                <span class="text-[10px] font-bold uppercase tracking-wider text-stone-500 flex items-center gap-1">
                                    <i class="ph-bold ph-phone-call text-amber-600"></i> Script de Ligação Fria (Parabéns pela Abertura)
                                </span>
                                <button onclick="navigator.clipboard.writeText(appState.radarResults[${idx}].cold_call_script); showToast('Script copiado!', 'success');" class="text-[10px] font-semibold text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-white flex items-center gap-1 cursor-pointer">
                                    <i class="ph ph-copy"></i> Copiar
                                </button>
                            </div>
                            <textarea readonly class="w-full text-xs font-mono p-2.5 rounded border border-stone-200 dark:border-darkborder bg-white dark:bg-darkbg text-stone-800 dark:text-stone-200 h-28 resize-none focus:outline-none">${escapeHtml(item.cold_call_script)}</textarea>
                        </div>

                        <div class="space-y-1">
                            <div class="flex items-center justify-between">
                                <span class="text-[10px] font-bold uppercase tracking-wider text-stone-500 flex items-center gap-1">
                                    <i class="ph-bold ph-whatsapp-logo text-emerald-600"></i> Mensagem WhatsApp (Oferta de Boas-Vindas R$ 1.000)
                                </span>
                                <button onclick="navigator.clipboard.writeText(appState.radarResults[${idx}].whatsapp_script); showToast('Mensagem copiada!', 'success');" class="text-[10px] font-semibold text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-white flex items-center gap-1 cursor-pointer">
                                    <i class="ph ph-copy"></i> Copiar
                                </button>
                            </div>
                            <textarea readonly class="w-full text-xs font-mono p-2.5 rounded border border-stone-200 dark:border-darkborder bg-white dark:bg-darkbg text-stone-800 dark:text-stone-200 h-28 resize-none focus:outline-none">${escapeHtml(item.whatsapp_script)}</textarea>
                        </div>
                    </div>

                    <!-- Card Actions -->
                    <div class="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-stone-100 dark:border-darkborder/60">
                        <div class="flex items-center gap-2">
                            <button onclick="toggleRadarPitch(${idx})" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-stone-100 dark:bg-darkborder text-stone-700 dark:text-stone-200 hover:bg-stone-200 dark:hover:bg-darkcard2 transition flex items-center gap-1.5 cursor-pointer">
                                <i class="ph-bold ph-sparkle text-amber-500"></i>
                                <span id="btnToggleRadarPitchText_${idx}">Ver Roteiro / Pitch</span>
                            </button>

                            ${item.phone && item.phone.length >= 10 ? `
                                <a href="https://wa.me/55${item.phone.replace(/\\D/g, '')}?text=${encodeURIComponent(item.whatsapp_script)}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 border border-emerald-200 dark:border-emerald-800/40 transition flex items-center gap-1">
                                    <i class="ph-bold ph-whatsapp-logo"></i>
                                    <span>WhatsApp</span>
                                </a>
                            ` : ''}
                        </div>

                        <div class="flex items-center gap-2">
                            <button onclick="importRadarLead(${idx}, false)" id="btnImportRadar_${idx}" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-white transition shadow-xs flex items-center gap-1 cursor-pointer">
                                <i class="ph-bold ph-plus-circle"></i>
                                <span>Importar p/ Leads</span>
                            </button>
                            <button onclick="importRadarLead(${idx}, true)" class="px-3 py-1.5 rounded-lg text-xs font-semibold border border-stone-300 dark:border-darkborder hover:border-stone-500 text-stone-800 dark:text-stone-200 bg-white dark:bg-darkcard transition flex items-center gap-1 cursor-pointer">
                                <i class="ph-bold ph-arrow-square-out"></i>
                                <span>Importar & Abrir Roteiro</span>
                            </button>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function toggleRadarPitch(idx) {
    const drawer = document.getElementById(`radarPitchDrawer_${idx}`);
    const textEl = document.getElementById(`btnToggleRadarPitchText_${idx}`);
    if (drawer) {
        drawer.classList.toggle('hidden');
        if (textEl) {
            textEl.innerText = drawer.classList.contains('hidden') ? 'Ver Roteiro / Pitch' : 'Ocultar Roteiro';
        }
    }
}

async function importRadarLead(idx, openScript = false) {
    const item = appState.radarResults[idx];
    if (!item) return;

    if (item._imported) {
        if (openScript && item._importedId) {
            openScriptModal(item._importedId);
        } else {
            showToast('Esta empresa já foi importada!', 'info');
        }
        return;
    }

    const btn = document.getElementById(`btnImportRadar_${idx}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<div class="inline-block w-2.5 h-2.5 border border-stone-200 border-t-transparent rounded-full animate-spin"></div> <span>Importando...</span>`;
    }

    try {
        const res = await fetch('/api/radar_cnpj/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item)
        });
        const data = await res.json();
        if (data.success) {
            item._imported = true;
            item._importedId = data.lead_id;
            if (btn) {
                btn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white flex items-center gap-1 cursor-default';
                btn.innerHTML = `<i class="ph-bold ph-check"></i> <span>Importado</span>`;
            }
            showToast(`${item.razao_social} adicionado à Central de Leads!`, 'success');
            loadLeadsTable();
            loadKpis();
            if (openScript && data.lead_id) {
                openScriptModal(data.lead_id);
            }
        } else {
            showToast(data.error || 'Erro ao importar empresa.', 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="ph-bold ph-plus-circle"></i> <span>Importar p/ Leads</span>`;
            }
        }
    } catch (err) {
        showToast('Erro de comunicação: ' + err.message, 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="ph-bold ph-plus-circle"></i> <span>Importar p/ Leads</span>`;
        }
    }
}

async function importAllRadarLeads() {
    const toImport = (appState.radarResults || []).map((item, idx) => ({ item, idx })).filter(x => !x.item._imported);
    if (toImport.length === 0) {
        showToast('Todas as empresas visíveis já foram importadas!', 'info');
        return;
    }

    const btn = document.getElementById('btnImportAllRadar');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<div class="inline-block w-3 h-3 border-2 border-stone-200 border-t-transparent rounded-full animate-spin"></div> <span>Importando...</span>`;
    }

    let count = 0;
    for (const { item, idx } of toImport) {
        try {
            const res = await fetch('/api/radar_cnpj/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item)
            });
            const data = await res.json();
            if (data.success) {
                item._imported = true;
                item._importedId = data.lead_id;
                const b = document.getElementById(`btnImportRadar_${idx}`);
                if (b) {
                    b.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white flex items-center gap-1 cursor-default';
                    b.innerHTML = `<i class="ph-bold ph-check"></i> <span>Importado</span>`;
                    b.disabled = true;
                }
                count++;
            }
        } catch (e) {
            console.error('Erro ao importar lead em lote:', e);
        }
    }

    if (btn) {
        btn.innerHTML = `<i class="ph-bold ph-check"></i> <span>${count} Importadas</span>`;
    }

    showToast(`${count} empresa(s) importada(s) com sucesso para a Central de Leads!`, 'success');
    loadLeadsTable();
    loadKpis();
}


// ----------------------------------------------------
// 20. AUDITOR DE PERFIS E LINKS NO INSTAGRAM CONTROLLER
// ----------------------------------------------------
appState.instagramResults = [];

async function handleInstagramScan(event) {
    if (event) event.preventDefault();

    const nicho = (document.getElementById('instaNicho')?.value || 'Dentista').trim();
    const cidade = (document.getElementById('instaCidade')?.value || 'Sorocaba').trim();
    const limite = parseInt(document.getElementById('instaLimite')?.value || '15', 10);

    if (!cidade || !nicho) {
        showToast('Informe o nicho e a cidade.', 'error');
        return;
    }

    const btn = document.getElementById('btnInstaScan');
    const btnText = document.getElementById('btnInstaScanText');
    const container = document.getElementById('instaResultsContainer');

    if (btn) btn.disabled = true;
    if (btnText) {
        btnText.innerHTML = `
            <span class="inline-flex items-center gap-1.5">
                <div class="w-3 h-3 border-2 border-white dark:border-stone-900 border-t-transparent rounded-full animate-spin"></div>
                <span>Auditando perfis e links...</span>
            </span>
        `;
    }

    if (container) {
        container.innerHTML = `
            <div class="glass-panel p-10 text-center rounded-xl space-y-3 border border-rose-200/50 dark:border-rose-900/30">
                <div class="inline-block w-8 h-8 border-3 border-rose-500 border-t-transparent rounded-full animate-spin"></div>
                <h4 class="font-bold text-xs text-stone-800 dark:text-stone-200 uppercase tracking-wider">
                    Minerando Perfis no Instagram & Auditando Saúde dos Links
                </h4>
                <p class="text-[11px] text-stone-500 max-w-md mx-auto">
                    Localizando perfis comerciais de <strong>${escapeHtml(nicho)}</strong> em <strong>${escapeHtml(cidade)}</strong> e testando status HTTP e links na bio em tempo real...
                </p>
            </div>
        `;
    }

    try {
        const res = await fetch('/api/instagram/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cidade,
                nicho,
                limite
            })
        });

        const data = await res.json();
        if (!data.success) {
            showToast(data.error || 'Erro na auditoria do Instagram.', 'error');
            if (container) {
                container.innerHTML = `
                    <div class="glass-panel p-8 text-center rounded-xl space-y-2 border border-dashed border-rose-300 dark:border-rose-900/50">
                        <i class="ph-bold ph-warning-octagon text-3xl text-rose-500"></i>
                        <h3 class="font-bold text-xs text-stone-800 dark:text-stone-200">Falha ao minerar Instagram</h3>
                        <p class="text-[11px] text-stone-500 max-w-md mx-auto">${escapeHtml(data.error || 'Tente novamente em instantes.')}</p>
                    </div>
                `;
            }
            return;
        }

        appState.instagramResults = data.perfis || [];
        renderInstagramResults(data);
        showToast(`${appState.instagramResults.length} perfis auditados com sucesso!`, 'success');
    } catch (err) {
        showToast('Falha na comunicação: ' + err.message, 'error');
        if (container) {
            container.innerHTML = `
                <div class="glass-panel p-8 text-center rounded-xl space-y-2 border border-dashed border-rose-300 dark:border-rose-900/50">
                    <i class="ph-bold ph-x-circle text-3xl text-rose-500"></i>
                    <h3 class="font-bold text-xs text-stone-800 dark:text-stone-200">Erro de rede</h3>
                    <p class="text-[11px] text-stone-500">${escapeHtml(err.message)}</p>
                </div>
            `;
        }
    } finally {
        if (btn) btn.disabled = false;
        if (btnText) btnText.innerHTML = 'Auditar Links do Instagram';
    }
}

function renderInstagramResults(data) {
    const container = document.getElementById('instaResultsContainer');
    if (!container) return;

    const perfis = data.perfis || [];
    if (perfis.length === 0) {
        container.innerHTML = `
            <div class="glass-panel p-8 text-center rounded-xl space-y-2 border border-dashed border-stone-300 dark:border-darkborder">
                <i class="ph-bold ph-magnifying-glass text-3xl text-stone-400"></i>
                <h3 class="font-bold text-xs text-stone-800 dark:text-stone-200">Nenhum perfil encontrado</h3>
                <p class="text-[11px] text-stone-500 max-w-md mx-auto">
                    Não encontramos perfis comerciais para ${escapeHtml(data.parametros.nicho)} em ${escapeHtml(data.parametros.cidade)}. Tente ajustar o nicho ou nome da cidade.
                </p>
            </div>
        `;
        return;
    }

    const stats = data.stats || { quebrados: 0, sem_link_ou_linktree: 0, ativos: 0 };

    container.innerHTML = `
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-3">
            <div class="glass-panel p-3 rounded-lg">
                <span class="text-[10px] font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider">Perfis Auditados</span>
                <div class="mt-0.5 text-xl font-bold font-mono text-stone-900 dark:text-white">${data.total}</div>
            </div>
            <div class="glass-panel p-3 rounded-lg border-rose-200 dark:border-rose-900/50 bg-rose-50/20 dark:bg-rose-950/10">
                <span class="text-[10px] font-semibold text-rose-700 dark:text-rose-400 uppercase tracking-wider flex items-center gap-1">
                    <i class="ph-bold ph-link-break"></i> Links Quebrados (404/DNS)
                </span>
                <div class="mt-0.5 text-xl font-bold font-mono text-rose-800 dark:text-rose-300">${stats.quebrados}</div>
            </div>
            <div class="glass-panel p-3 rounded-lg">
                <span class="text-[10px] font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1">
                    <i class="ph-bold ph-tree-structure"></i> Sem Site / Linktree
                </span>
                <div class="mt-0.5 text-xl font-bold font-mono text-amber-800 dark:text-amber-300">${stats.sem_link_ou_linktree}</div>
            </div>
            <div class="glass-panel p-3 rounded-lg">
                <span class="text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider flex items-center gap-1">
                    <i class="ph-bold ph-check-circle"></i> Sites Ativos
                </span>
                <div class="mt-0.5 text-xl font-bold font-mono text-emerald-800 dark:text-emerald-300">${stats.ativos}</div>
            </div>
        </div>

        ${stats.quebrados > 0 ? `
            <div class="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800/40 flex flex-wrap items-center justify-between gap-3 mb-3 shadow-xs">
                <div class="flex items-center gap-2.5">
                    <div class="w-7 h-7 rounded-full bg-rose-100 dark:bg-rose-900/50 text-rose-600 flex items-center justify-center shrink-0">
                        <i class="ph-bold ph-warning-octagon text-base"></i>
                    </div>
                    <div>
                        <h4 class="text-xs font-bold text-rose-950 dark:text-rose-200">
                            ${stats.quebrados} perfil(is) com link fora do ar ou quebrado na bio!
                        </h4>
                        <p class="text-[11px] text-rose-800/80 dark:text-rose-300/80">
                            Essas empresas estão perdendo clientes todos os dias. Oportunidade perfeita para a Landing Page de R$ 1.000.
                        </p>
                    </div>
                </div>
                <button onclick="importAllBrokenInstagramLeads()" id="btnImportBrokenInsta" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white transition shadow-xs flex items-center gap-1 shrink-0 cursor-pointer">
                    <i class="ph-bold ph-download-simple"></i>
                    <span>Importar Quebrados (${stats.quebrados})</span>
                </button>
            </div>
        ` : ''}

        <div class="grid grid-cols-1 gap-3">
            ${perfis.map((item, idx) => {
                let badgeClass = 'bg-stone-100 text-stone-700 dark:bg-darkcard2 dark:text-stone-300';
                let badgeIcon = 'ph-link';
                if (item.link_categoria === 'quebrado') {
                    badgeClass = 'bg-rose-100 dark:bg-rose-950/50 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-900/60 font-bold';
                    badgeIcon = 'ph-link-break';
                } else if (item.link_categoria === 'linktree' || item.link_categoria === 'apenas_whatsapp') {
                    badgeClass = 'bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-900/60 font-medium';
                    badgeIcon = 'ph-tree-structure';
                } else if (item.link_categoria === 'ativo') {
                    badgeClass = 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900/60 font-medium';
                    badgeIcon = 'ph-check-circle';
                }

                return `
                <div class="glass-panel p-4 rounded-xl border border-stone-200 dark:border-darkborder space-y-3 hover:border-stone-400 transition" id="instaCard_${idx}">
                    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-2.5">
                        <div class="space-y-1">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="px-2 py-0.5 rounded text-[10px] ${badgeClass} flex items-center gap-1 font-mono">
                                    <i class="ph-bold ${badgeIcon}"></i>
                                    <span>${escapeHtml(item.link_diagnostico)}</span>
                                </span>
                                <a href="${item.instagram_url}" target="_blank" rel="noopener noreferrer" class="text-xs font-bold text-rose-600 dark:text-rose-400 hover:underline flex items-center gap-1 font-mono">
                                    <i class="ph-bold ph-instagram-logo"></i> ${escapeHtml(item.handle)}
                                </a>
                            </div>
                            <h3 class="font-bold text-sm text-stone-900 dark:text-white leading-snug">${escapeHtml(item.nome)}</h3>
                            <p class="text-[11px] text-stone-500 dark:text-stone-400 leading-relaxed">${escapeHtml(item.bio_resumo)}</p>
                        </div>
                        <div class="flex items-center gap-1.5 shrink-0 self-start">
                            <span class="px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-stone-100 dark:bg-darkcard2 text-stone-800 dark:text-stone-200 border border-stone-200 dark:border-darkborder">
                                ${item.lead_score} pts
                            </span>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1 text-xs">
                        <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200/80 dark:border-darkborder/80 space-y-0.5 sm:col-span-2">
                            <span class="text-[10px] uppercase font-bold text-stone-400 flex items-center gap-1">
                                <i class="ph-bold ph-link"></i> Link Cadastrado na Bio
                            </span>
                            <p class="font-medium font-mono text-stone-800 dark:text-stone-200 truncate" title="${escapeHtml(item.link_bio || 'Sem link')}">
                                ${item.link_bio ? `<a href="${item.link_bio}" target="_blank" rel="noopener noreferrer" class="text-stone-700 dark:text-stone-300 hover:underline truncate">${escapeHtml(item.link_bio)}</a>` : '<span class="text-stone-400 italic font-sans">Nenhum link na bio</span>'}
                            </p>
                            <p class="text-[10.5px] text-stone-500 pt-0.5">${escapeHtml(item.link_detalhe)}</p>
                        </div>

                        <div class="p-2.5 rounded-lg bg-[#FAF9F6] dark:bg-darkbg border border-stone-200/80 dark:border-darkborder/80 space-y-0.5">
                            <span class="text-[10px] uppercase font-bold text-stone-400 flex items-center gap-1">
                                <i class="ph-bold ph-phone"></i> Telefone / WhatsApp
                            </span>
                            <p class="font-medium font-mono text-stone-800 dark:text-stone-200 truncate">
                                ${item.phone ? escapeHtml(item.phone) : '<span class="text-stone-400 italic font-sans">Direct no Instagram</span>'}
                            </p>
                        </div>
                    </div>

                    <!-- Expandable Pitch Drawer -->
                    <div id="instaPitchDrawer_${idx}" class="hidden p-3.5 rounded-lg bg-[#F5F3EF] dark:bg-darkcard2 border border-stone-200 dark:border-darkborder space-y-3">
                        <div class="space-y-1">
                            <div class="flex items-center justify-between">
                                <span class="text-[10px] font-bold uppercase tracking-wider text-stone-500 flex items-center gap-1">
                                    <i class="ph-bold ph-phone-call text-rose-600"></i> Script de Ligação / Abordagem
                                </span>
                                <button onclick="navigator.clipboard.writeText(appState.instagramResults[${idx}].cold_call_script); showToast('Script copiado!', 'success');" class="text-[10px] font-semibold text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-white flex items-center gap-1 cursor-pointer">
                                    <i class="ph ph-copy"></i> Copiar
                                </button>
                            </div>
                            <textarea readonly class="w-full text-xs font-mono p-2.5 rounded border border-stone-200 dark:border-darkborder bg-white dark:bg-darkbg text-stone-800 dark:text-stone-200 h-28 resize-none focus:outline-none">${escapeHtml(item.cold_call_script)}</textarea>
                        </div>

                        <div class="space-y-1">
                            <div class="flex items-center justify-between">
                                <span class="text-[10px] font-bold uppercase tracking-wider text-stone-500 flex items-center gap-1">
                                    <i class="ph-bold ph-whatsapp-logo text-emerald-600"></i> Mensagem WhatsApp / Direct (Oferta R$ 1.000)
                                </span>
                                <button onclick="navigator.clipboard.writeText(appState.instagramResults[${idx}].whatsapp_script); showToast('Mensagem copiada!', 'success');" class="text-[10px] font-semibold text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-white flex items-center gap-1 cursor-pointer">
                                    <i class="ph ph-copy"></i> Copiar
                                </button>
                            </div>
                            <textarea readonly class="w-full text-xs font-mono p-2.5 rounded border border-stone-200 dark:border-darkborder bg-white dark:bg-darkbg text-stone-800 dark:text-stone-200 h-28 resize-none focus:outline-none">${escapeHtml(item.whatsapp_script)}</textarea>
                        </div>
                    </div>

                    <!-- Card Actions -->
                    <div class="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-stone-100 dark:border-darkborder/60">
                        <div class="flex items-center gap-2">
                            <button onclick="toggleInstaPitch(${idx})" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-stone-100 dark:bg-darkborder text-stone-700 dark:text-stone-200 hover:bg-stone-200 dark:hover:bg-darkcard2 transition flex items-center gap-1.5 cursor-pointer">
                                <i class="ph-bold ph-sparkle text-rose-500"></i>
                                <span id="btnToggleInstaPitchText_${idx}">Ver Roteiro / Pitch</span>
                            </button>

                            <a href="${item.instagram_url}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-stone-100 dark:bg-darkcard2 text-stone-700 dark:text-stone-300 hover:bg-stone-200 border border-stone-200 dark:border-darkborder transition flex items-center gap-1">
                                <i class="ph-bold ph-arrow-square-out"></i>
                                <span>Abrir Perfil</span>
                            </a>

                            ${item.phone && item.phone.length >= 10 ? `
                                <a href="https://wa.me/55${item.phone.replace(/\\D/g, '')}?text=${encodeURIComponent(item.whatsapp_script)}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 border border-emerald-200 dark:border-emerald-800/40 transition flex items-center gap-1">
                                    <i class="ph-bold ph-whatsapp-logo"></i>
                                    <span>WhatsApp</span>
                                </a>
                            ` : ''}
                        </div>

                        <div class="flex items-center gap-2">
                            <button onclick="importInstagramLead(${idx}, false)" id="btnImportInsta_${idx}" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-white transition shadow-xs flex items-center gap-1 cursor-pointer">
                                <i class="ph-bold ph-plus-circle"></i>
                                <span>Importar p/ Leads</span>
                            </button>
                            <button onclick="importInstagramLead(${idx}, true)" class="px-3 py-1.5 rounded-lg text-xs font-semibold border border-stone-300 dark:border-darkborder hover:border-stone-500 text-stone-800 dark:text-stone-200 bg-white dark:bg-darkcard transition flex items-center gap-1 cursor-pointer">
                                <i class="ph-bold ph-arrow-square-out"></i>
                                <span>Importar & Abrir Roteiro</span>
                            </button>
                        </div>
                    </div>
                </div>
                `;
            }).join('')}
        </div>
    `;
}

function toggleInstaPitch(idx) {
    const drawer = document.getElementById(`instaPitchDrawer_${idx}`);
    const textEl = document.getElementById(`btnToggleInstaPitchText_${idx}`);
    if (drawer) {
        drawer.classList.toggle('hidden');
        if (textEl) {
            textEl.innerText = drawer.classList.contains('hidden') ? 'Ver Roteiro / Pitch' : 'Ocultar Roteiro';
        }
    }
}

async function importInstagramLead(idx, openScript = false) {
    const item = appState.instagramResults[idx];
    if (!item) return;

    if (item._imported) {
        if (openScript && item._importedId) {
            openScriptModal(item._importedId);
        } else {
            showToast('Este perfil já foi importado!', 'info');
        }
        return;
    }

    const btn = document.getElementById(`btnImportInsta_${idx}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<div class="inline-block w-2.5 h-2.5 border border-stone-200 border-t-transparent rounded-full animate-spin"></div> <span>Importando...</span>`;
    }

    try {
        const res = await fetch('/api/instagram/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item)
        });
        const data = await res.json();
        if (data.success) {
            item._imported = true;
            item._importedId = data.lead_id;
            if (btn) {
                btn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white flex items-center gap-1 cursor-default';
                btn.innerHTML = `<i class="ph-bold ph-check"></i> <span>Importado</span>`;
            }
            showToast(`Perfil @${item.handle_raw} importado para a Central de Leads!`, 'success');
            loadLeadsTable();
            loadKpis();
            if (openScript && data.lead_id) {
                openScriptModal(data.lead_id);
            }
        } else {
            showToast(data.error || 'Erro ao importar perfil.', 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="ph-bold ph-plus-circle"></i> <span>Importar p/ Leads</span>`;
            }
        }
    } catch (err) {
        showToast('Erro de comunicação: ' + err.message, 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="ph-bold ph-plus-circle"></i> <span>Importar p/ Leads</span>`;
        }
    }
}

async function importAllBrokenInstagramLeads() {
    const toImport = (appState.instagramResults || []).map((item, idx) => ({ item, idx }))
        .filter(x => x.item.link_categoria === 'quebrado' && !x.item._imported);
    if (toImport.length === 0) {
        showToast('Nenhum link quebrado pendente de importação.', 'info');
        return;
    }

    const btn = document.getElementById('btnImportBrokenInsta');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<div class="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div> <span>Importando...</span>`;
    }

    let count = 0;
    for (const { item, idx } of toImport) {
        try {
            const res = await fetch('/api/instagram/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item)
            });
            const data = await res.json();
            if (data.success) {
                item._imported = true;
                item._importedId = data.lead_id;
                const b = document.getElementById(`btnImportInsta_${idx}`);
                if (b) {
                    b.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white flex items-center gap-1 cursor-default';
                    b.innerHTML = `<i class="ph-bold ph-check"></i> <span>Importado</span>`;
                    b.disabled = true;
                }
                count++;
            }
        } catch (e) {
            console.error('Erro ao importar perfil:', e);
        }
    }

    if (btn) {
        btn.innerHTML = `<i class="ph-bold ph-check"></i> <span>${count} Importados</span>`;
    }

    showToast(`${count} leads com link quebrado importados com sucesso!`, 'success');
    loadLeadsTable();
    loadKpis();
}
