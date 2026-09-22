// FraudForces JavaScript Application Logic

const API_BASE = "";
let currentPage = 1;
let totalPages = 1;

// Preset definitions covering 38 loan features
const PRESETS = {
    low_risk: {
        disbursed_amount: 45000,
        asset_cost: 65000,
        ltv: 69.23,
        branch_id: 67,
        supplier_id: 22807,
        manufacturer_id: 45,
        current_pincode_id: 1441,
        date_of_birth: "15-06-1988",
        employment_type: "Salaried",
        disbursal_date: "10-10-2018",
        state_id: 6,
        employee_code_id: 1998,
        mobileno_avl_flag: 1,
        aadhar_flag: 1,
        pan_flag: 0,
        voterid_flag: 0,
        driving_flag: 0,
        passport_flag: 0,
        perform_cns_score: 785,
        perform_cns_score_description: "A-Very Low Risk",
        pri_no_of_accts: 3,
        pri_active_accts: 2,
        pri_overdue_accts: 0,
        pri_current_balance: 15000,
        pri_sanctioned_amount: 50000,
        pri_disbursed_amount: 50000,
        sec_no_of_accts: 0,
        sec_active_accts: 0,
        sec_overdue_accts: 0,
        sec_current_balance: 0,
        sec_sanctioned_amount: 0,
        sec_disbursed_amount: 0,
        primary_instal_amt: 2500,
        sec_instal_amt: 0,
        new_accts_in_last_six_months: 1,
        delinquent_accts_in_last_six_months: 0,
        average_acct_age: "2yrs 1mon",
        credit_history_length: "3yrs 4mon",
        no_of_inquiries: 0
    },
    borderline: {
        disbursed_amount: 55000,
        asset_cost: 68000,
        ltv: 80.88,
        branch_id: 67,
        supplier_id: 22807,
        manufacturer_id: 45,
        current_pincode_id: 1441,
        date_of_birth: "12-08-1992",
        employment_type: "Self employed",
        disbursal_date: "10-10-2018",
        state_id: 6,
        employee_code_id: 1998,
        mobileno_avl_flag: 1,
        aadhar_flag: 1,
        pan_flag: 0,
        voterid_flag: 0,
        driving_flag: 0,
        passport_flag: 0,
        perform_cns_score: 0,
        perform_cns_score_description: "No Bureau History Available",
        pri_no_of_accts: 0,
        pri_active_accts: 0,
        pri_overdue_accts: 0,
        pri_current_balance: 0,
        pri_sanctioned_amount: 0,
        pri_disbursed_amount: 0,
        sec_no_of_accts: 0,
        sec_active_accts: 0,
        sec_overdue_accts: 0,
        sec_current_balance: 0,
        sec_sanctioned_amount: 0,
        sec_disbursed_amount: 0,
        primary_instal_amt: 0,
        sec_instal_amt: 0,
        new_accts_in_last_six_months: 0,
        delinquent_accts_in_last_six_months: 0,
        average_acct_age: "0yrs 0mon",
        credit_history_length: "0yrs 0mon",
        no_of_inquiries: 0
    },
    high_risk: {
        disbursed_amount: 85000,
        asset_cost: 92000,
        ltv: 92.39,
        branch_id: 67,
        supplier_id: 22807,
        manufacturer_id: 45,
        current_pincode_id: 1441,
        date_of_birth: "25-11-1999",
        employment_type: "Self employed",
        disbursal_date: "10-10-2018",
        state_id: 6,
        employee_code_id: 1998,
        mobileno_avl_flag: 1,
        aadhar_flag: 1,
        pan_flag: 0,
        voterid_flag: 0,
        driving_flag: 0,
        passport_flag: 0,
        perform_cns_score: 310,
        perform_cns_score_description: "M-High Risk",
        pri_no_of_accts: 6,
        pri_active_accts: 4,
        pri_overdue_accts: 3,
        pri_current_balance: 110000,
        pri_sanctioned_amount: 120000,
        pri_disbursed_amount: 120000,
        sec_no_of_accts: 1,
        sec_active_accts: 1,
        sec_overdue_accts: 1,
        sec_current_balance: 15000,
        sec_sanctioned_amount: 15000,
        sec_disbursed_amount: 15000,
        primary_instal_amt: 7500,
        sec_instal_amt: 1200,
        new_accts_in_last_six_months: 3,
        delinquent_accts_in_last_six_months: 2,
        average_acct_age: "0yrs 6mon",
        credit_history_length: "0yrs 9mon",
        no_of_inquiries: 4
    }
};

let currentPayload = { ...PRESETS.low_risk };

// Initialize page
document.addEventListener("DOMContentLoaded", () => {
    applyPreset("low_risk");
    checkAuthStatus();
    checkHealth();
});

// View switcher (tabs)
function switchView(viewName) {
    document.getElementById("viewSubmit").style.display = viewName === "submit" ? "block" : "none";
    document.getElementById("viewHistory").style.display = viewName === "history" ? "block" : "none";
    document.getElementById("viewModel").style.display = viewName === "model" ? "block" : "none";

    document.getElementById("tabSubmit").classList.toggle("active", viewName === "submit");
    document.getElementById("tabHistory").classList.toggle("active", viewName === "history");
    document.getElementById("tabModel").classList.toggle("active", viewName === "model");

    if (viewName === "history") {
        loadSubmissions(1);
    }
}

// Preset application
function applyPreset(presetKey) {
    const preset = PRESETS[presetKey];
    if (!preset) return;
    currentPayload = JSON.parse(JSON.stringify(preset));

    document.getElementById("disbursed_amount").value = preset.disbursed_amount;
    document.getElementById("asset_cost").value = preset.asset_cost;
    document.getElementById("ltv").value = preset.ltv;
    document.getElementById("employment_type").value = preset.employment_type;
    document.getElementById("date_of_birth").value = preset.date_of_birth;
    document.getElementById("disbursal_date").value = preset.disbursal_date;
    document.getElementById("bureau_score").value = preset.perform_cns_score;
    document.getElementById("bureau_score_description").value = preset.perform_cns_score_description;
    document.getElementById("no_of_inquiries").value = preset.no_of_inquiries;
    document.getElementById("pri_active_accts").value = preset.pri_active_accts;
    document.getElementById("pri_overdue_accts").value = preset.pri_overdue_accts;
    document.getElementById("pri_current_balance").value = preset.pri_current_balance;
    document.getElementById("credit_history_length").value = preset.credit_history_length;
    document.getElementById("average_acct_age").value = preset.average_acct_age;
    document.getElementById("state_id").value = preset.state_id;

    document.getElementById("rawJsonInput").value = JSON.stringify(currentPayload, null, 2);
}

// Toggle JSON view
function toggleJsonEditor() {
    const container = document.getElementById("jsonEditorContainer");
    const isHidden = container.style.display === "none";
    container.style.display = isHidden ? "block" : "none";
    if (isHidden) {
        syncFormToJson();
    }
}

function syncFormToJson() {
    currentPayload.disbursed_amount = parseFloat(document.getElementById("disbursed_amount").value);
    currentPayload.asset_cost = parseFloat(document.getElementById("asset_cost").value);
    currentPayload.ltv = parseFloat(document.getElementById("ltv").value);
    currentPayload.employment_type = document.getElementById("employment_type").value;
    currentPayload.date_of_birth = document.getElementById("date_of_birth").value;
    currentPayload.disbursal_date = document.getElementById("disbursal_date").value;
    currentPayload.perform_cns_score = parseInt(document.getElementById("bureau_score").value, 10);
    currentPayload.perform_cns_score_description = document.getElementById("bureau_score_description").value;
    currentPayload.no_of_inquiries = parseInt(document.getElementById("no_of_inquiries").value, 10);
    currentPayload.pri_active_accts = parseInt(document.getElementById("pri_active_accts").value, 10);
    currentPayload.pri_overdue_accts = parseInt(document.getElementById("pri_overdue_accts").value, 10);
    currentPayload.pri_current_balance = parseFloat(document.getElementById("pri_current_balance").value);
    currentPayload.credit_history_length = document.getElementById("credit_history_length").value;
    currentPayload.average_acct_age = document.getElementById("average_acct_age").value;
    currentPayload.state_id = parseInt(document.getElementById("state_id").value, 10);

    document.getElementById("rawJsonInput").value = JSON.stringify(currentPayload, null, 2);
}

// Authentication handling
function getToken() {
    return localStorage.getItem("cf_jwt_token");
}

function setToken(token) {
    localStorage.setItem("cf_jwt_token", token);
}

function removeToken() {
    localStorage.removeItem("cf_jwt_token");
    localStorage.removeItem("cf_user_email");
}

async function checkAuthStatus() {
    const token = getToken();
    const guestView = document.getElementById("authGuestView");
    const userView = document.getElementById("authUserView");
    const sidebarProfile = document.getElementById("sidebarProfileBody");

    if (!token) {
        guestView.style.display = "inline";
        userView.style.display = "none";
        sidebarProfile.innerHTML = `
            <p style="color: #666; font-size: 11px;">Not currently authenticated.</p>
            <div style="margin-top: 8px;">
                <a href="/login" class="cf-button" style="text-decoration: none;">Sign In</a>
                <a href="/register" class="cf-button-secondary" style="margin-left: 6px; text-decoration: none;">Register</a>
            </div>
        `;
        return;
    }

    try {
        const res = await fetch("/v1/users/me", {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (res.ok) {
            const user = await res.json();
            localStorage.setItem("cf_user_email", user.email);
            guestView.style.display = "none";
            userView.style.display = "inline";

            const emailParts = user.email.split("@")[0];
            const handle = emailParts.length > 15 ? emailParts.substring(0, 15) + "..." : emailParts;

            document.getElementById("userRankTitle").textContent = handle;
            document.getElementById("userEmailLink").textContent = user.email;

            sidebarProfile.innerHTML = `
                <ul class="sidebar-list">
                    <li><span>Handle:</span> <strong class="user-handle rank-specialist">${handle}</strong></li>
                    <li><span>Email:</span> <span style="font-size: 11px;">${user.email}</span></li>
                    <li><span>Role:</span> <span>${user.role || 'Credit Analyst'}</span></li>
                    <li><span>Status:</span> <span style="color: #008000; font-weight: bold;">Active</span></li>
                </ul>
                <div style="margin-top: 10px;">
                    <button class="cf-button-secondary" onclick="handleLogout()" style="width: 100%;">Sign Out</button>
                </div>
            `;
        } else {
            removeToken();
            checkAuthStatus();
        }
    } catch (e) {
        console.warn("Auth check failed:", e);
    }
}

async function handleLoginSubmit(event) {
    event.preventDefault();
    const alertBox = document.getElementById("loginAlert");
    alertBox.style.display = "none";

    const email = document.getElementById("loginEmail").value;
    const password = document.getElementById("loginPassword").value;

    try {
        const res = await fetch("/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();
        if (res.ok) {
            setToken(data.access_token);
            closeModal("loginModal");
            checkAuthStatus();
            loadSubmissions(1);
        } else {
            alertBox.textContent = data.message || data.detail || "Authentication failed.";
            alertBox.style.display = "block";
        }
    } catch (err) {
        alertBox.textContent = "Network error connecting to API.";
        alertBox.style.display = "block";
    }
}

async function handleRegisterSubmit(event) {
    event.preventDefault();
    const alertBox = document.getElementById("registerAlert");
    alertBox.style.display = "none";

    const email = document.getElementById("registerEmail").value;
    const password = document.getElementById("registerPassword").value;

    try {
        const res = await fetch("/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();
        if (res.ok) {
            // Auto-login after registration
            const loginRes = await fetch("/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password })
            });
            const loginData = await loginRes.json();
            if (loginRes.ok) {
                setToken(loginData.access_token);
            }
            closeModal("registerModal");
            checkAuthStatus();
        } else {
            alertBox.textContent = data.message || data.detail || "Registration failed.";
            alertBox.style.display = "block";
        }
    } catch (err) {
        alertBox.textContent = "Network error connecting to API.";
        alertBox.style.display = "block";
    }
}

function handleLogout() {
    removeToken();
    checkAuthStatus();
    switchView("submit");
}

// Scoring submission
async function handleScoreSubmit(event) {
    event.preventDefault();

    const alertBox = document.getElementById("submitAlert");
    alertBox.style.display = "none";

    // Synchronize payload from either json box or inputs
    if (document.getElementById("jsonEditorContainer").style.display !== "none") {
        try {
            currentPayload = JSON.parse(document.getElementById("rawJsonInput").value);
        } catch (e) {
            alertBox.textContent = "Invalid JSON in raw payload editor.";
            alertBox.style.display = "block";
            return;
        }
    } else {
        syncFormToJson();
    }

    // Ensure user has auth token
    let token = getToken();
    if (!token) {
        alertBox.innerHTML = `Please <a href="/login">sign in</a> or <a href="/register">register</a> to submit loan scoring evaluations.`;
        alertBox.style.display = "block";
        return;
    }

    const btn = document.getElementById("btnSubmitScore");
    const statusMsg = document.getElementById("scoringStatus");
    btn.disabled = true;
    statusMsg.textContent = "Executing ML risk pipeline...";

    const startTime = performance.now();

    try {
        const res = await fetch("/v1/score", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(currentPayload)
        });

        const elapsedMs = Math.round(performance.now() - startTime);
        const data = await res.json();

        if (res.ok) {
            displayVerdict(data, elapsedMs);
            statusMsg.textContent = `Completed in ${elapsedMs} ms`;
            alertBox.style.display = "none";
            loadSubmissions(1);
        } else {
            alertBox.textContent = `Scoring Error: ${data.message || data.detail || "Inference failed"}`;
            alertBox.style.display = "block";
            statusMsg.textContent = "Error";
        }
    } catch (err) {
        alertBox.textContent = `Network error: ${err.message}`;
        alertBox.style.display = "block";
        statusMsg.textContent = "Connection error";
    } finally {
        btn.disabled = false;
    }
}

// Display Verdict Banner (Codeforces Judge Style)
function displayVerdict(data, elapsedMs) {
    const banner = document.getElementById("verdictBanner");
    const badge = document.getElementById("verdictBadge");
    const timeSpan = document.getElementById("verdictTime");
    const scoreSpan = document.getElementById("verdictScore");
    const probText = document.getElementById("verdictProbText");
    const meter = document.getElementById("probMeterFill");
    const auditId = document.getElementById("verdictAuditId");

    const prob = (typeof data.probability === "number") ? data.probability : 
                 (typeof data.fraud_probability === "number") ? data.fraud_probability : 0;
    const pct = (prob * 100).toFixed(2);
    probText.textContent = `${pct}%`;
    scoreSpan.textContent = `Score: ${prob.toFixed(4)}`;
    timeSpan.textContent = `Latency: ${elapsedMs} ms`;
    auditId.textContent = data.request_id || data.id || "N/A";

    meter.style.width = `${Math.min(pct, 100)}%`;

    badge.className = "verdict-badge";
    if (data.decision === "APPROVE") {
        badge.textContent = "ACCEPTED (APPROVE)";
        badge.classList.add("verdict-approve");
        meter.style.backgroundColor = "#008000";
    } else if (data.decision === "DENY") {
        badge.textContent = "WRONG ANSWER (DENY)";
        badge.classList.add("verdict-deny");
        meter.style.backgroundColor = "#CC0000";
    } else {
        badge.textContent = "JUDGEMENT PENDING (REVIEW)";
        badge.classList.add("verdict-review");
        meter.style.backgroundColor = "#1756A5";
    }

    banner.style.display = "block";
    banner.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Submission history table
async function loadSubmissions(page = 1) {
    const token = getToken();
    const tbody = document.getElementById("submissionsTableBody");
    const paginationInfo = document.getElementById("paginationInfo");

    if (!token) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; color: #777; padding: 20px;">
                    Please <a href="javascript:void(0)" onclick="openModal('loginModal')">Sign In</a> to view your submissions history.
                </td>
            </tr>
        `;
        return;
    }

    currentPage = page;
    const filter = document.getElementById("filterDecision").value;
    let url = `/v1/scores?page=${page}&size=10`;
    if (filter) url += `&decision=${filter}`;

    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 15px; color: #666;">Loading submissions...</td></tr>`;

    try {
        const res = await fetch(url, {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (!res.ok) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #c00; padding: 15px;">Failed to load submissions.</td></tr>`;
            return;
        }

        const data = await res.json();
        totalPages = data.total_pages || 1;

        paginationInfo.textContent = `Page ${data.page} of ${totalPages} (Total: ${data.total} submissions)`;
        document.getElementById("btnPrevPage").disabled = data.page <= 1;
        document.getElementById("btnNextPage").disabled = data.page >= totalPages;

        if (!data.items || data.items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #777; padding: 20px;">No submissions found.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.items.map(item => {
            const reqId = item.request_id || item.id || "";
            const shortId = reqId ? reqId.substring(0, 8) : "N/A";
            const ts = item.created_at ? new Date(item.created_at).toISOString().replace("T", " ").substring(0, 19) : "--";
            const itemProb = (typeof item.probability === "number") ? item.probability : 
                             (typeof item.fraud_probability === "number") ? item.fraud_probability : 0;
            const probStr = (itemProb * 100).toFixed(2) + "%";

            let pillClass = "pill-yellow";
            let verdictLabel = item.decision || "REVIEW";
            if (item.decision === "APPROVE") {
                pillClass = "pill-green";
            } else if (item.decision === "DENY") {
                pillClass = "pill-red";
            }

            return `
                <tr>
                    <td class="mono"><a href="javascript:void(0)" onclick="showSubmissionDetails('${reqId}')">${shortId}</a></td>
                    <td class="mono" style="font-size: 11px;">${ts}</td>
                    <td class="mono">${item.applicant_id || 'APPL-' + shortId}</td>
                    <td><span class="rule-pill ${pillClass}">${verdictLabel}</span></td>
                    <td class="mono">${probStr}</td>
                    <td class="mono" style="font-size: 11px;">${item.model_version || 'v1-baseline'}</td>
                    <td>
                        <button class="cf-button-secondary" onclick="showSubmissionDetails('${reqId}')">View</button>
                        <button class="cf-button-danger" onclick="deleteSubmission('${reqId}')">Delete</button>
                    </td>
                </tr>
            `;
        }).join("");

    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #c00; padding: 15px;">Network error: ${err.message}</td></tr>`;
    }
}

function changePage(delta) {
    const target = currentPage + delta;
    if (target >= 1 && target <= totalPages) {
        loadSubmissions(target);
    }
}

async function showSubmissionDetails(scoreId) {
    const token = getToken();
    try {
        const res = await fetch(`/v1/scores/${scoreId}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            document.getElementById("detailsJsonContent").textContent = JSON.stringify(data, null, 2);
            openModal("detailsModal");
        }
    } catch (e) {
        alert("Failed to fetch details: " + e.message);
    }
}

async function deleteSubmission(scoreId) {
    if (!confirm("Are you sure you want to delete this scoring submission record?")) return;
    const token = getToken();
    try {
        const res = await fetch(`/v1/scores/${scoreId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            loadSubmissions(currentPage);
        } else {
            alert("Failed to delete record.");
        }
    } catch (e) {
        alert("Error deleting record: " + e.message);
    }
}

// Health check ping
async function checkHealth() {
    const sService = document.getElementById("healthService");
    const sDb = document.getElementById("healthDatabase");
    const sModel = document.getElementById("healthModel");
    const sLatency = document.getElementById("healthLatency");

    sDb.textContent = "Pinging...";
    const t0 = performance.now();

    try {
        const res = await fetch("/health/ready");
        const elapsed = Math.round(performance.now() - t0);
        sLatency.textContent = `${elapsed} ms`;

        if (res.ok) {
            const data = await res.json();
            sService.innerHTML = `<span style="color: #008000; font-weight: bold;">Online</span>`;
            sDb.innerHTML = `<span style="color: #008000; font-weight: bold;">Connected (pg:16)</span>`;
            sModel.innerHTML = `<span style="color: #008000; font-weight: bold;">Loaded (${data.model_version || 'v1'})</span>`;
        } else {
            sDb.innerHTML = `<span style="color: #CC0000; font-weight: bold;">Degraded (503)</span>`;
        }
    } catch (e) {
        sDb.innerHTML = `<span style="color: #CC0000; font-weight: bold;">Unreachable</span>`;
        sLatency.textContent = "Timeout";
    }
}

// Modal management
function openModal(id) {
    document.getElementById(id).style.display = "flex";
}

function closeModal(id) {
    document.getElementById(id).style.display = "none";
}

window.onclick = function(event) {
    if (event.target.classList && event.target.classList.contains("modal-overlay")) {
        event.target.style.display = "none";
    }
};
