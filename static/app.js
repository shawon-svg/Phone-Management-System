const $ = (selector) => document.querySelector(selector);
const money = (value) => Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
let inventory = [];

async function api(path, options) {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Something went wrong.');
    return data;
}
function toast(message) { const node = $('#toast'); node.textContent = message; node.style.display = 'block'; setTimeout(() => node.style.display = 'none', 2500); }
function itemCard(item, sell = false) { return `<article class="item"><div><h3>${esc(item.model)}${sell ? '' : ` · ${esc(item.sl_no)}`}</h3><p>${esc(item.chipset)} · ${esc(item.ram)} · ${esc(item.storage)} · ${esc(item.color)}<br>${sell ? `${item.quantity} in stock` : `IMEI ${esc(item.imei)} · ${item.quantity} units`}</p></div>${sell ? `<button class="primary small sell-one" data-id="${item.id}">Sell</button>` : `<strong>${money(item.sell_price)}</strong>`}</article>`; }
async function loadInventory() { inventory = await api('/api/inventory?q=' + encodeURIComponent($('#stock-search').value)); $('#stock-list').innerHTML = inventory.length ? inventory.map(item => itemCard(item)).join('') : '<p class="item">No stock found.</p>'; const available = inventory.filter(item => item.quantity > 0); $('#checkout-list').innerHTML = available.length ? available.map(item => itemCard(item, true)).join('') : '<p class="item">No stock available to sell.</p>'; }
async function loadDashboard() { const [items, summary, sales] = await Promise.all([api('/api/inventory'), api('/api/summary'), api('/api/sales')]); $('#stat-stock').textContent = items.reduce((sum, item) => sum + item.quantity, 0); $('#stat-value').textContent = money(items.reduce((sum, item) => sum + item.quantity * item.cost_price, 0)); $('#stat-sold').textContent = summary.units_sold; $('#stat-profit').textContent = money(summary.total_profit); $('#recent-sales').innerHTML = sales.slice(0, 5).map(sale => `<article class="item"><div><h3>${esc(sale.model)} ×${sale.quantity}</h3><p>${esc(sale.sold_at)}</p></div><strong>${money(sale.profit)}</strong></article>`).join('') || '<p>No sales recorded yet.</p>'; }
async function loadHistory() { const sales = await api('/api/sales'); $('#history-list').innerHTML = sales.map(sale => `<article class="item"><div><h3>${esc(sale.model)} ×${sale.quantity}</h3><p>${esc(sale.chipset)} · ${esc(sale.ram)} · ${esc(sale.storage)}<br>${esc(sale.sold_at)}</p></div><strong>${money(sale.profit)}</strong></article>`).join('') || '<p class="item">No sales recorded yet.</p>'; }
async function refresh() { await Promise.all([loadInventory(), loadDashboard(), loadHistory()]); }
function showView(name) { document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === name)); document.querySelectorAll('.nav button').forEach(button => button.classList.toggle('active', button.dataset.view === name)); }

document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
$('#refresh').addEventListener('click', () => refresh().then(() => toast('Updated')));
$('#stock-search').addEventListener('input', loadInventory);
$('#checkout-search').addEventListener('input', async () => { const query = $('#checkout-search').value.toLowerCase(); const rows = inventory.filter(item => JSON.stringify(item).toLowerCase().includes(query) && item.quantity > 0); $('#checkout-list').innerHTML = rows.map(item => itemCard(item, true)).join('') || '<p class="item">No matching stock.</p>'; });
$('#open-add').addEventListener('click', () => $('#add-dialog').showModal());
$('#add-form').addEventListener('submit', async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { await api('/api/inventory', { method: 'POST', body: JSON.stringify(data) }); event.target.reset(); $('#add-dialog').close(); await refresh(); toast('Stock saved'); } catch (error) { toast(error.message); } });
document.addEventListener('click', async (event) => { const button = event.target.closest('.sell-one'); if (!button) return; const quantity = prompt('Quantity to sell:', '1'); if (quantity === null) return; try { await api('/api/sales', { method: 'POST', body: JSON.stringify({ item_id: button.dataset.id, quantity }) }); await refresh(); toast('Sale saved to history'); } catch (error) { toast(error.message); } });
refresh().catch(error => toast(error.message));