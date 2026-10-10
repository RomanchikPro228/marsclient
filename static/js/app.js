/**
 * MarsClient Web Portal - Frontend Script
 * Handles Authentication, UI Views, Modals, FunPay Redirects, Admin Panel & Toast Notifications
 */

const FUNPAY_URL = "https://funpay.com/uk/users/14128634/";
let currentUser = null;

// ==========================================
// 1. Инициализация при загрузке страницы
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    checkAuth();
    setupEscapeModalClose();
});

// Закрытие модалок по клавише ESC и клику вне окна
function setupEscapeModalClose() {
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            document.querySelectorAll(".modal.active").forEach((m) => m.classList.remove("active"));
        }
    });

    document.querySelectorAll(".modal").forEach((modal) => {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                modal.classList.remove("active");
            }
        });
    });
}

// ==========================================
// 2. Уведомления (Toast Notifications)
// ==========================================
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "error") icon = "❌";
    if (type === "warning") icon = "⚠️";

    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-msg">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("hide");
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

// ==========================================
// 3. Управление окнами (Modals)
// ==========================================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add("active");
        const firstInput = modal.querySelector("input:not([type=hidden])");
        if (firstInput) firstInput.focus();
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove("active");
}

function switchModal(fromId, toId) {
    closeModal(fromId);
    setTimeout(() => openModal(toId), 150);
}

function openLogoutModal() {
    openModal("logoutConfirmModal");
}

// ==========================================
// 4. Переключение разделов (Views)
// ==========================================
function switchView(viewName) {
    const views = {
        home: document.getElementById("homeView"),
        store: document.getElementById("storeView"),
        cabinet: document.getElementById("cabinetView"),
        admin: document.getElementById("adminView")
    };

    // Проверка доступа
    if (viewName === "admin" && (!currentUser || currentUser.is_admin !== 1)) {
        showToast("Доступ к панели владельца запрещен!", "error");
        return;
    }

    if ((viewName === "cabinet" || viewName === "store") && !currentUser) {
        // Если гость пытается зайти в кабинет, открываем окно логина
        openModal("loginModal");
        return;
    }

    // Скрываем все разделы
    Object.values(views).forEach((v) => {
        if (v) v.classList.remove("active");
    });

    // Активируем нужный
    if (views[viewName]) {
        views[viewName].classList.add("active");
    }

    // Обновляем активную вкладку в навбаре
    const navBtns = {
        store: document.getElementById("navStoreBtn"),
        cabinet: document.getElementById("navCabinetBtn"),
        admin: document.getElementById("navAdminBtn")
    };

    Object.values(navBtns).forEach((b) => {
        if (b) b.classList.remove("active");
    });

    if (navBtns[viewName]) {
        navBtns[viewName].classList.add("active");
    }

    // Если открыли админку — подгружаем свежие данные
    if (viewName === "admin") {
        loadAdminData();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ==========================================
// 5. Проверка сессии (Auth Check)
// ==========================================
async function checkAuth() {
    try {
        const res = await fetch("/api/me", { method: "GET" });
        if (res.ok) {
            const data = await res.json();
            currentUser = data;
            renderUserLoggedIn(data);
        } else {
            currentUser = null;
            renderGuest();
        }
    } catch (e) {
        currentUser = null;
        renderGuest();
    }
}

function renderUserLoggedIn(user) {
    const guestNav = document.getElementById("guestNav");
    const authNav = document.getElementById("authNav");
    const userNavBadge = document.getElementById("userNavBadge");
    const navAdminBtn = document.getElementById("navAdminBtn");

    if (guestNav) guestNav.style.display = "none";
    if (authNav) authNav.style.display = "flex";
    if (userNavBadge) userNavBadge.style.display = "flex";

    // Имя и дни в навбаре
    const badgeUsername = document.getElementById("badgeUsername");
    const badgeDays = document.getElementById("badgeDays");
    if (badgeUsername) badgeUsername.innerText = user.username;
    if (badgeDays) badgeDays.innerText = `${user.remaining_days} дн.`;

    // Админская кнопка
    if (navAdminBtn) {
        navAdminBtn.style.display = user.is_admin === 1 ? "inline-flex" : "none";
    }

    // Личный кабинет
    const cabUsername = document.getElementById("cabUsername");
    const cabEmail = document.getElementById("cabEmail");
    const cabHwid = document.getElementById("cabHwid");
    const cabAvatarLetter = document.getElementById("cabAvatarLetter");
    const cabRoleBadge = document.getElementById("cabRoleBadge");
    const subStatusText = document.getElementById("subStatusText");
    const subDaysCount = document.getElementById("subDaysCount");
    const subStatusIndicator = document.getElementById("subStatusIndicator");

    if (cabUsername) cabUsername.innerText = user.username;
    if (cabEmail) cabEmail.innerText = user.email;
    if (cabHwid) cabHwid.innerText = user.hwid || "Не привязан (запустите лаунчер)";
    if (cabAvatarLetter) cabAvatarLetter.innerText = user.username.charAt(0).toUpperCase();

    if (cabRoleBadge) {
        if (user.is_admin === 1) {
            cabRoleBadge.innerText = "⭐ ВЛАДЕЛЕЦ";
            cabRoleBadge.className = "dash-user-role role-admin";
        } else {
            cabRoleBadge.innerText = "Пользователь";
            cabRoleBadge.className = "dash-user-role";
        }
    }

    // Статус подписки
    if (user.is_active) {
        if (subStatusText) subStatusText.innerText = "АКТИВНА";
        if (subDaysCount) subDaysCount.innerText = `${user.remaining_days} дн. осталось`;
        if (subStatusIndicator) {
            subStatusIndicator.className = "status-indicator active";
        }
    } else {
        if (subStatusText) subStatusText.innerText = "ИСТЕКЛА / НЕ АКТИВНА";
        if (subDaysCount) subDaysCount.innerText = "0 дней";
        if (subStatusIndicator) {
            subStatusIndicator.className = "status-indicator expired";
        }
    }

    // Если сейчас на главной странице для гостей — автоматически показываем кабинет
    const homeView = document.getElementById("homeView");
    if (homeView && homeView.classList.contains("active")) {
        switchView("cabinet");
    }
}

function renderGuest() {
    const guestNav = document.getElementById("guestNav");
    const authNav = document.getElementById("authNav");
    const userNavBadge = document.getElementById("userNavBadge");
    const navAdminBtn = document.getElementById("navAdminBtn");

    if (guestNav) guestNav.style.display = "flex";
    if (authNav) authNav.style.display = "none";
    if (userNavBadge) userNavBadge.style.display = "none";
    if (navAdminBtn) navAdminBtn.style.display = "none";

    switchView("home");
}

// ==========================================
// 6. Регистрация
// ==========================================
async function handleRegister(e) {
    e.preventDefault();
    const email = document.getElementById("regEmail").value.trim();
    const username = document.getElementById("regUsername").value.trim();
    const password = document.getElementById("regPassword").value.trim();
    const btn = document.getElementById("regSubmitBtn");

    if (!email || !username || !password) {
        showToast("Заполните все поля регистрации!", "error");
        return;
    }

    btn.disabled = true;
    btn.innerText = "Создание аккаунта...";

    try {
        const res = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, username, password })
        });
        const data = await res.json();

        if (res.ok) {
            closeModal("registerModal");
            showToast(data.message, "success");
            await checkAuth();
            switchView("cabinet");
        } else {
            showToast(data.detail || "Ошибка регистрации", "error");
        }
    } catch (err) {
        showToast("Ошибка соединения с сервером!", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Зарегистрироваться";
    }
}

// ==========================================
// 7. Подтверждение почты кодом
// ==========================================
async function handleVerifyEmail(e) {
    e.preventDefault();
    const email = document.getElementById("verifyEmailHidden").value;
    const code = document.getElementById("verifyCodeInput").value.trim();
    const btn = document.getElementById("verifySubmitBtn");

    if (!code) {
        showToast("Введите проверочный код!", "warning");
        return;
    }

    btn.disabled = true;
    btn.innerText = "Проверка кода...";

    try {
        const res = await fetch("/api/verify_email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, code })
        });
        const data = await res.json();

        if (res.ok) {
            closeModal("verifyModal");
            showToast(data.message, "success");
            await checkAuth();
            switchView("store"); // сразу предлагаем купить или активировать
        } else {
            showToast(data.detail || "Неверный проверочный код!", "error");
        }
    } catch (err) {
        showToast("Ошибка соединения с сервером!", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Подтвердить и войти";
    }
}

// ==========================================
// 8. Вход (Login)
// ==========================================
async function handleLogin(e) {
    e.preventDefault();
    const identInput = document.getElementById("loginIdentifier");
    const emailInput = document.getElementById("loginEmail");
    const userInput = document.getElementById("loginUsername");
    const ident = (identInput ? identInput.value : (emailInput ? emailInput.value : (userInput ? userInput.value : ""))).trim();
    const password = document.getElementById("loginPassword").value.trim();
    const btn = document.getElementById("loginSubmitBtn");

    if (!ident || !password) {
        showToast("Введите логин или почту и пароль!", "warning");
        return;
    }

    btn.disabled = true;
    btn.innerText = "Вход...";

    try {
        const res = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ login: ident, email: ident, username: ident, password: password })
        });
        const data = await res.json();

        if (res.ok) {
            closeModal("loginModal");
            showToast(data.message, "success");
            await checkAuth();
            switchView("cabinet");
        } else {
            showToast(data.detail || "Ошибка входа в аккаунт", "error");
        }
    } catch (err) {
        showToast("Ошибка соединения с сервером!", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Войти в аккаунт";
    }
}

// ==========================================
// 9. Выход из аккаунта (Logout)
// ==========================================
async function executeLogout() {
    closeModal("logoutConfirmModal");
    try {
        const res = await fetch("/api/logout", { method: "POST" });
        if (res.ok) {
            currentUser = null;
            renderGuest();
            showToast("Вы успешно вышли из аккаунта.", "info");
        }
    } catch (err) {
        currentUser = null;
        renderGuest();
    }
}

// ==========================================
// 10. Переход на покупку в FunPay
// Ссылка скрыта от глаз, переход моментальный
// ==========================================
function redirectToFunPay(plan) {
    // Тихо открываем страницу FunPay владельца
    window.open(FUNPAY_URL, "_blank");
    showToast("Переход на безопасную оплату FunPay...", "info");
}

// ==========================================
// 11. Активация ключа FunPay
// ==========================================
async function handleActivateKey(e) {
    e.preventDefault();
    const keyInput = document.getElementById("keyInput");
    const btn = document.getElementById("activateBtn");
    const keyCode = keyInput.value.trim().toUpperCase();

    if (!keyCode) {
        showToast("Введите ключ активации!", "warning");
        return;
    }

    btn.disabled = true;
    btn.innerText = "Активация...";

    try {
        const res = await fetch("/api/activate_key", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ key_code: keyCode })
        });
        const data = await res.json();

        if (res.ok) {
            showToast(data.message, "success");
            keyInput.value = "";
            await checkAuth();
        } else {
            showToast(data.detail || "Неверный или использованный ключ!", "error");
        }
    } catch (err) {
        showToast("Ошибка связи с сервером!", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Активировать ключ";
    }
}

// ==========================================
// 12. Смена пароля
// ==========================================
async function handleChangePassword(e) {
    e.preventDefault();
    const old_password = document.getElementById("oldPwd").value;
    const new_password = document.getElementById("newPwd").value;

    try {
        const res = await fetch("/api/change_password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ old_password, new_password })
        });
        const data = await res.json();

        if (res.ok) {
            closeModal("changePasswordModal");
            document.getElementById("oldPwd").value = "";
            document.getElementById("newPwd").value = "";
            showToast(data.message, "success");
        } else {
            showToast(data.detail || "Ошибка смены пароля", "error");
        }
    } catch (err) {
        showToast("Ошибка связи с сервером!", "error");
    }
}

// ==========================================
// 13. Смена почты
// ==========================================
async function handleChangeEmail(e) {
    e.preventDefault();
    const new_email = document.getElementById("newEmailInput").value.trim();
    const password = document.getElementById("emailConfirmPwd").value;

    try {
        const res = await fetch("/api/change_email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_email, password })
        });
        const data = await res.json();

        if (res.ok) {
            closeModal("changeEmailModal");
            document.getElementById("newEmailInput").value = "";
            document.getElementById("emailConfirmPwd").value = "";
            showToast(data.message, "success");
            await checkAuth();
        } else {
            showToast(data.detail || "Ошибка смены почты", "error");
        }
    } catch (err) {
        showToast("Ошибка связи с сервером!", "error");
    }
}

// ==========================================
// 14. Скачивание лаунчера
// ==========================================
async function downloadLauncher() {
    try {
        const res = await fetch("/api/download_launcher", { method: "GET" });
        const data = await res.json();

        if (res.ok) {
            showToast("Загрузка клиента MarsClient началась!", "success");
            const link = document.createElement("a");
            link.href = data.download_url;
            link.download = data.filename || "MarsClient.jar";
            document.body.appendChild(link);
            link.click();
            link.remove();
        } else {
            showToast(data.detail || "Для скачивания требуется активная подписка!", "error");
        }
    } catch (err) {
        showToast("Ошибка запроса на скачивание!", "error");
    }
}

async function downloadSetup() {
    try {
        const res = await fetch("/api/download_setup", { method: "GET" });
        if (res.ok) {
            showToast("Завантаження MarsClient.jar та авто-скрипта почалося!", "info");

            // 1. Завантажуємо сам файл MarsClient.jar
            const linkJar = document.createElement("a");
            linkJar.href = "/static/updates/MarsClient.jar";
            linkJar.download = "MarsClient.jar";
            document.body.appendChild(linkJar);
            linkJar.click();
            linkJar.remove();

            // 2. Завантажуємо скрипт MotionBlur_Setup.bat
            const blob = await res.blob();
            setTimeout(() => {
                const linkBat = document.createElement("a");
                linkBat.href = URL.createObjectURL(blob);
                linkBat.download = "MotionBlur_Setup.bat";
                document.body.appendChild(linkBat);
                linkBat.click();
                linkBat.remove();
                showToast("MarsClient.jar та MotionBlur_Setup.bat завантажено! Запустіть .bat файл для авто-налаштування.", "success");
            }, 300);
        } else {
            const data = await res.json().catch(() => ({}));
            showToast(data.detail || "Для завантаження потрібна активна підписка!", "error");
        }
    } catch (err) {
        showToast("Помилка завантаження!", "error");
    }
}

async function downloadManualWithGuide() {
    try {
        const res = await fetch("/api/download_manual", { method: "GET" });
        if (res.ok) {
            showToast("Завантаження MarsClient.jar почалося!", "success");
            const blob = await res.blob();
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = "MarsClient.jar";
            document.body.appendChild(link);
            link.click();
            link.remove();

            // Автоматично підставляємо дані у підказку ліцензії в інструкції
            const hint = document.getElementById("guideLicenseHint");
            if (hint && currentUser) {
                hint.innerText = `${currentUser.email}:${currentUser.username}:ВАШ_ПАРОЛЬ`;
            }

            // Відкриваємо модалку з повною зрозумілою інструкцією прямо на екрані
            openModal("manualInstructionModal");
        } else {
            const data = await res.json().catch(() => ({}));
            showToast(data.detail || "Для завантаження потрібна активна підписка!", "error");
        }
    } catch (err) {
        showToast("Помилка завантаження MarsClient.jar!", "error");
    }
}

function copyText(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showToast("Шлях скопійовано!", "success");
        }).catch(() => {
            prompt("Скопіюйте цей шлях:", text);
        });
    } else {
        prompt("Скопіюйте цей шлях:", text);
    }
}

async function handleUserResetHwid() {
    if (!confirm("Ви дійсно хочете скинути прив'язку HWID? При наступному запуску чит автоматично прив'яжеться до вашого поточного ПК.")) {
        return;
    }
    try {
        const res = await fetch("/api/user/reset_hwid", { method: "POST" });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "success");
            checkAuth();
        } else {
            showToast(data.detail || "Помилка скидання HWID!", "error");
        }
    } catch (err) {
        showToast("Помилка підключення до сервера!", "error");
    }
}

// ==========================================
// 15. Админ-панель: Генерация ключей для FunPay
// ==========================================
async function handleAdminGenKeys(e) {
    e.preventDefault();
    const days = parseInt(document.getElementById("genDays").value, 10);
    const count = parseInt(document.getElementById("genCount").value, 10) || 1;

    try {
        const res = await fetch("/api/admin/generate_keys", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ days, count })
        });
        const data = await res.json();

        if (res.ok) {
            const resultBox = document.getElementById("genResultBox");
            const textarea = document.getElementById("genKeysTextarea");
            textarea.value = data.keys.join("\n");
            resultBox.style.display = "block";
            showToast(`Сгенерировано ключей: ${data.keys.length}`, "success");
        } else {
            showToast(data.detail || "Ошибка генерации ключей", "error");
        }
    } catch (err) {
        showToast("Ошибка соединения с сервером!", "error");
    }
}

function copyGeneratedKeys() {
    const textarea = document.getElementById("genKeysTextarea");
    if (!textarea || !textarea.value) return;
    navigator.clipboard.writeText(textarea.value).then(() => {
        showToast("Все ключи скопированы в буфер обмена!", "success");
    }).catch(() => {
        textarea.select();
        document.execCommand("copy");
        showToast("Ключи скопированы!", "success");
    });
}

// ==========================================
// 16. Админ-панель: Загрузка пользователей
// ==========================================
async function loadAdminData() {
    const tbody = document.getElementById("adminUsersTbody");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="loading-td">Загрузка данных...</td></tr>';

    try {
        const res = await fetch("/api/admin/data", { method: "GET" });
        if (!res.ok) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-td error">Ошибка загрузки данных</td></tr>';
            return;
        }

        const data = await res.json();
        const users = data.users || [];

        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-td">Пользователей пока нет</td></tr>';
            return;
        }

        tbody.innerHTML = users.map((u) => {
            const isBanned = u.is_banned === 1;
            const statusBadge = isBanned 
                ? '<span class="table-badge badge-banned">Бан</span>'
                : (u.days_left > 0 ? '<span class="table-badge badge-active">Активен</span>' : '<span class="table-badge badge-inactive">Истек</span>');

            const hwidDisplay = u.hwid ? `<span class="hwid-short" title="${u.hwid}">${u.hwid.substring(0, 10)}...</span>` : '<span class="text-muted">Нет</span>';
            const banBtnText = isBanned ? "Разбанить" : "Бан";
            const banBtnClass = isBanned ? "btn-mini btn-action-unban" : "btn-mini btn-action-ban";

            return `
                <tr>
                    <td>#${u.id}</td>
                    <td><strong>${escapeHtml(u.username)}</strong> ${u.is_admin === 1 ? '<span class="admin-star">★</span>' : ''}</td>
                    <td>${escapeHtml(u.email)}</td>
                    <td><strong>${u.days_left}</strong> дн.</td>
                    <td>${hwidDisplay}</td>
                    <td>${statusBadge}</td>
                    <td class="action-buttons-cell">
                        <button class="btn-mini" onclick="adminUserAction('${escapeHtml(u.username)}', 'add_days', 30)" title="Додати 30 днів">+30д</button>
                        <button class="btn-mini" style="background: rgba(239, 68, 68, 0.2); border-color: rgba(239, 68, 68, 0.4);" onclick="adminUserAction('${escapeHtml(u.username)}', 'remove_days', 30)" title="Забрати 30 днів">-30д</button>
                        <button class="btn-mini" onclick="promptChangeDays('${escapeHtml(u.username)}')" title="Вказати свою кількість днів">±Дні</button>
                        <button class="btn-mini" onclick="adminUserAction('${escapeHtml(u.username)}', 'reset_hwid')">Сброс HWID</button>
                        <button class="${banBtnClass}" onclick="adminUserAction('${escapeHtml(u.username)}', 'toggle_ban')">${banBtnText}</button>
                        <button class="btn-mini btn-action-delete" style="background: rgba(239, 68, 68, 0.35); border-color: rgba(239, 68, 68, 0.6); color: #fca5a5;" onclick="if(confirm('Ви точно хочете назавжди видалити користувача ${escapeHtml(u.username)}?')) adminUserAction('${escapeHtml(u.username)}', 'delete_user')" title="Видалити користувача">Видалити</button>
                    </td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-td error">Сбой подключения</td></tr>';
    }

    // Завантажуємо статус релізів
    loadAdminReleases();
}

// Завантаження статусу версій оновлень
async function loadAdminReleases() {
    try {
        const res = await fetch("/api/admin/releases");
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById("activeReleaseBadge");
            const statusText = document.getElementById("updaterStatusText");

            if (data.latest) {
                const ver = data.latest.version || "1.0.0";
                if (badge) {
                    badge.innerText = `Поточна версія: v${ver}`;
                }
                if (statusText) {
                    const dateStr = data.latest.created_at ? new Date(data.latest.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";
                    statusText.innerText = `Версія v${ver} активна для всіх гравців ${dateStr ? `(оновлено о ${dateStr})` : ''}`;
                }
            } else if (badge) {
                badge.innerText = "Поточна версія: v1.0.0";
            }
        }
    } catch (e) {}
}

// Публікація оновлення клієнта в 1 клік
async function handleOneClickUpdate() {
    const btn = document.getElementById("oneClickUpdateBtn");
    const statusText = document.getElementById("updaterStatusText");
    if (!btn) return;

    btn.disabled = true;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="btn-glow-icon">⏳</span> <span>Оновлення реєструється...</span>';

    if (statusText) {
        statusText.innerText = "Публікація нової версії на сервері...";
    }

    try {
        const res = await fetch("/api/admin/publish_latest_update", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await res.json();

        if (res.ok) {
            showToast(data.message || "Оновлення успішно опубліковано для ВСІХ гравців!", "success");
            await loadAdminReleases();
        } else {
            showToast(data.detail || "Помилка при публікації оновлення", "error");
            if (statusText) {
                statusText.innerText = "Помилка при публікації. Спробуйте ще раз.";
            }
        }
    } catch (err) {
        showToast("Помилка зв'язку з сервером!", "error");
        if (statusText) {
            statusText.innerText = "Помилка підключення до сервера.";
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

// Действия администратора над пользователем
async function adminUserAction(username, action, days = 0) {
    try {
        const res = await fetch("/api/admin/user_action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, action, days })
        });
        const data = await res.json();

        if (res.ok) {
            showToast(data.message, "success");
            loadAdminData();
            // Если изменили себя — обновляем статус
            if (currentUser && currentUser.username === username) {
                checkAuth();
            }
        } else {
            showToast(data.detail || "Ошибка выполнения действия", "error");
        }
    } catch (err) {
        showToast("Ошибка соединения!", "error");
    }
}

function promptChangeDays(username) {
    const val = prompt(`Зміна підписки для ${username}.\nВведіть кількість днів (наприклад, 15 щоб додати, або -10 щоб забрати, або 0 щоб повністю зняти підписку):`, "30");
    if (val === null) return;
    const trimmed = val.trim();
    if (!trimmed) return;
    const num = parseInt(trimmed, 10);
    if (isNaN(num)) {
        alert("Будь ласка, введіть числове значення!");
        return;
    }
    if (num > 0) {
        adminUserAction(username, 'add_days', num);
    } else if (num < 0) {
        adminUserAction(username, 'remove_days', Math.abs(num));
    } else {
        adminUserAction(username, 'clear_sub');
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}
