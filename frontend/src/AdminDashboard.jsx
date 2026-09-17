import { useCallback, useEffect, useState } from 'react';

import { api, clearSession, getSession, money } from './api';

const VIEWS = ['Overview', 'Inventory', 'Leads', 'Bookings', 'Analytics'];
const ENDPOINTS = {
  Inventory: '/api/admin/inventory',
  Leads: '/api/admin/leads',
  Bookings: '/api/admin/appointments',
};

function Icon({ name }) {
  const paths = {
    grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
    car: 'M4 16h16l-1.5-6-2-3h-9l-2 3L4 16Zm3 0v3m10-3v3M6 12h12',
    users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8',
    calendar: 'M3 5h18v16H3zM8 3v4m8-4v4M3 10h18',
    chart: 'M4 20V10m6 10V4m6 16v-7m4 7H2',
    logout: 'M10 17l5-5-5-5m5 5H3m14-8h4v16h-4',
    arrow: 'M5 12h14m-5-5 5 5-5 5',
    menu: 'M4 7h16M4 12h16M4 17h16',
    close: 'M6 6l12 12M18 6 6 18',
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name]} /></svg>;
}

function Status({ value }) {
  return <em className={`status ${String(value).toLowerCase().replaceAll(' ', '-')}`}>{value}</em>;
}

function AdminState({ type, onRetry }) {
  const copy = type === 'loading'
    ? ['Loading live operations data', 'Retrieving verified dealership records.']
    : type === 'empty'
      ? ['No records found', 'There are no records to display in this workspace.']
      : ['Dashboard data is unavailable', 'Please try again in a moment.'];
  return <section className="admin-empty-state" role={type === 'error' ? 'alert' : 'status'}>
    <i />
    <h2>{copy[0]}</h2>
    <p>{copy[1]}</p>
    {type === 'error' && <button className="outline" onClick={onRetry}>Try again</button>}
  </section>;
}

function Overview({ data, changeView }) {
  const cards = [
    ['Total inventory', data.vehicles, 'car'],
    ['Available inventory', data.available_vehicles, 'grid'],
    ['Leads', data.leads, 'users'],
    ['Bookings', data.appointments, 'calendar'],
    ['Customers', data.customers, 'users'],
  ];
  return <>
    <section className="admin-hero">
      <div><span className="kicker">LIVE BUSINESS CONTROL</span><h2>Every customer conversation,<br />connected to an outcome.</h2><p>Monitor verified inventory, buyer intent and booking activity from the production database.</p></div>
      <span className="hero-n">N</span>
    </section>
    <div className="metric-grid admin-summary-grid">
      {cards.map(([label, value, icon]) => <article key={label}><Icon name={icon} /><small>{label}</small><b>{Number(value || 0).toLocaleString()}</b><span>Production database</span></article>)}
    </div>
    <div className="admin-panels">
      <section><span className="kicker">BOOKING STATUS</span><h3>{Number(data.confirmed_appointments || 0).toLocaleString()} confirmed bookings</h3><p>Requested bookings can be approved or rejected from the Bookings workspace.</p><button onClick={() => changeView('Bookings')}>Review bookings <Icon name="arrow" /></button></section>
      <section><span className="kicker">LEAD PRIORITY</span><h3>{Number(data.hot_leads || 0).toLocaleString()} hot leads</h3><p>Review active buyer intent and follow-up work in the leads workspace.</p><button onClick={() => changeView('Leads')}>Review leads <Icon name="arrow" /></button></section>
    </div>
  </>;
}

function ConfirmationModal({ request, busy, error, onCancel, onConfirm }) {
  if (!request) return null;
  const booking = request.kind === 'booking';
  return <div className="modal-backdrop" role="presentation">
    <section className="admin-confirmation" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <span className="kicker">CONFIRM DELETION</span>
      <h2 id="confirm-title">Delete this {booking ? 'booking' : 'lead'}?</h2>
      <p>{booking ? 'This will permanently remove the booking record.' : 'This action cannot be undone.'}</p>
      <p className="admin-confirmation-id">{booking ? request.row.appointment_id : request.row.lead_id}</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer><button className="outline" onClick={onCancel} disabled={busy}>Cancel</button><button className="admin-delete" onClick={onConfirm} disabled={busy}>{busy ? 'Deleting…' : 'Delete'}</button></footer>
    </section>
  </div>;
}

function BookingActions({ row, busy, onApprove, onReject, onDelete }) {
  const requested = row.status === 'Requested';
  return <div className="admin-row-actions">
    {requested && <><button className="gold compact" onClick={() => onApprove(row)} disabled={busy}>Approve</button><button className="outline compact" onClick={() => onReject(row)} disabled={busy}>Reject</button></>}
    <button className="admin-delete compact" onClick={() => onDelete(row)} disabled={busy}>Delete</button>
  </div>;
}

function Table({ view, rows, busyId, onApprove, onReject, onDelete }) {
  if (!rows.length) return <AdminState type="empty" />;
  if (view === 'Bookings') return <div className="data-table"><table><thead><tr><th>Booking</th><th>Customer</th><th>Vehicle</th><th>Date & time</th><th>Salesperson</th><th>Status</th><th>Actions</th></tr></thead><tbody>
    {rows.map(row => <tr key={row.appointment_id}><td data-label="Booking">{row.appointment_id}</td><td data-label="Customer">{row.customer_id}</td><td data-label="Vehicle">{row.vehicle_id}</td><td data-label="Date & time">{row.appointment_date}<small>{String(row.appointment_time || '').slice(0, 5)}</small></td><td data-label="Salesperson">{row.salesperson_id}</td><td data-label="Status"><Status value={row.status} /></td><td data-label="Actions"><BookingActions row={row} busy={busyId === row.appointment_id} onApprove={onApprove} onReject={onReject} onDelete={onDelete} /></td></tr>)}
  </tbody></table></div>;
  if (view === 'Leads') return <div className="data-table"><table><thead><tr><th>Lead</th><th>Customer</th><th>Status</th><th>Budget</th><th>Temperature</th><th>Salesperson</th><th>Actions</th></tr></thead><tbody>
    {rows.map(row => <tr key={row.lead_id}><td data-label="Lead">{row.lead_id}</td><td data-label="Customer">{row.customer_id}</td><td data-label="Status"><Status value={row.lead_status} /></td><td data-label="Budget">{money(row.budget)}</td><td data-label="Temperature"><Status value={row.lead_temperature} /></td><td data-label="Salesperson">{row.assigned_salesperson}</td><td data-label="Actions"><button className="admin-delete compact" onClick={() => onDelete(row)} disabled={busyId === row.lead_id}>Delete</button></td></tr>)}
  </tbody></table></div>;
  return <div className="data-table"><table><thead><tr><th>Vehicle</th><th>Model</th><th>Condition</th><th>Price</th><th>Status</th><th>Location</th></tr></thead><tbody>
    {rows.map(row => <tr key={row.vehicle_id}><td data-label="Vehicle">{row.vehicle_id}</td><td data-label="Model"><b>{row.year} {row.make} {row.model}</b><small>{row.trim}</small></td><td data-label="Condition"><Status value={row.condition} /></td><td data-label="Price">{money(row.sale_price)}</td><td data-label="Status"><Status value={row.vehicle_status} /></td><td data-label="Location">{row.dealership_location}</td></tr>)}
  </tbody></table></div>;
}

function Analytics({ data }) {
  return <section className="analytics-top"><article><small>Tracked calls</small><b>{data.calls?.total || 0}</b><span>Persisted voice outcomes</span></article><article><small>Total leads</small><b>{data.leads?.total || 0}</b><span>Current production records</span></article><article><small>Average buyer budget</small><b>{money(data.leads?.average_budget)}</b><span>Across CRM records</span></article><article><small>Bookings</small><b>{data.appointments?.total || 0}</b><span>Current production records</span></article></section>;
}

export function AdminDashboard() {
  const [view, setView] = useState('Overview');
  const [state, setState] = useState('loading');
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState('');
  const [confirmation, setConfirmation] = useState(null);
  const [confirmationError, setConfirmationError] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const session = getSession();

  const load = useCallback(async () => {
    setState('loading'); setError('');
    try {
      if (view === 'Overview') setSummary(await api('/api/admin/summary', {}, true));
      else if (view === 'Analytics') setAnalytics(await api('/api/admin/analytics', {}, true));
      else setRows((await api(`${ENDPOINTS[view]}?limit=75`, {}, true)).records || []);
      setState('ready');
    } catch (requestError) {
      if (requestError.status === 401) { clearSession(); window.history.replaceState({}, '', '/admin/login'); window.dispatchEvent(new Event('popstate')); return; }
      setError(requestError.message); setState('error');
    }
  }, [view]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    const closeMenu = event => { if (event.key === 'Escape') setMenuOpen(false); };
    window.addEventListener('keydown', closeMenu);
    return () => window.removeEventListener('keydown', closeMenu);
  }, []);

  const changeView = nextView => { setView(nextView); setNotice(''); setConfirmation(null); setMenuOpen(false); };
  const updateBooking = async (row, action) => {
    setBusyId(row.appointment_id); setNotice('');
    try {
      const result = await api(`/api/admin/appointments/${row.appointment_id}/${action}`, { method: 'PATCH' }, true);
      const updated = result.booking;
      setRows(current => current.map(item => item.appointment_id === updated.appointment_id ? updated : item));
      setNotice(result.message);
    } catch (requestError) { setNotice(requestError.message); } finally { setBusyId(''); }
  };
  const confirmDelete = async () => {
    const { kind, row } = confirmation;
    const id = kind === 'booking' ? row.appointment_id : row.lead_id;
    const path = kind === 'booking' ? `/api/admin/appointments/${id}` : `/api/admin/leads/${id}`;
    setBusyId(id); setConfirmationError('');
    try {
      await api(path, { method: 'DELETE' }, true);
      setRows(current => current.filter(item => (kind === 'booking' ? item.appointment_id : item.lead_id) !== id));
      setConfirmation(null); setNotice(`${kind === 'booking' ? 'Booking' : 'Lead'} deleted.`);
    } catch (requestError) { setConfirmationError(requestError.message); } finally { setBusyId(''); }
  };
  const content = state === 'loading' ? <AdminState type="loading" /> : state === 'error' ? <AdminState type="error" onRetry={load} /> : view === 'Overview' ? <Overview data={summary || {}} changeView={changeView} /> : view === 'Analytics' ? <Analytics data={analytics || {}} /> : <Table view={view} rows={rows} busyId={busyId} onApprove={row => updateBooking(row, 'approve')} onReject={row => updateBooking(row, 'reject')} onDelete={row => { setConfirmation({ kind: view === 'Bookings' ? 'booking' : 'lead', row }); setConfirmationError(''); }} />;
  return <div className={`admin-shell ${menuOpen ? 'admin-menu-open' : ''}`}><button className="admin-menu-backdrop" aria-label="Close admin navigation" tabIndex={menuOpen ? 0 : -1} onClick={() => setMenuOpen(false)} /><aside aria-label="Admin navigation"><div className="admin-brand"><span>N</span><b>NEXDRIVE</b><button className="admin-menu-close" aria-label="Close admin navigation" onClick={() => setMenuOpen(false)}><Icon name="close" /></button></div><div className="admin-location"><i /><span><small>FLAGSHIP LOCATION</small><b>Plano, Texas</b></span></div><nav>{VIEWS.map(item => <button key={item} className={view === item ? 'active' : ''} onClick={() => changeView(item)}>{item}</button>)}</nav><div className="admin-user"><span>{session?.user?.email?.slice(0, 2).toUpperCase() || 'NE'}</span><div><b>Operations admin</b><small>{session?.user?.email || 'Secured session'}</small></div><button aria-label="Sign out" onClick={() => { clearSession(); window.history.replaceState({}, '', '/admin/login'); window.dispatchEvent(new Event('popstate')); }}><Icon name="logout" /></button></div></aside><main><header><button className="admin-menu-toggle" aria-label="Open admin navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Icon name="menu" /></button><div className="admin-heading"><span className="kicker">NEXDRIVE OPERATIONS</span><h1>{view === 'Overview' ? 'Command center' : view}</h1></div><div className="live"><i /> Live Supabase</div></header>{notice && <div className="notice" role="status">{notice}<button aria-label="Dismiss notification" onClick={() => setNotice('')}>×</button></div>}{error && state === 'error' && <p className="admin-error-detail">{error}</p>}{content}</main><ConfirmationModal request={confirmation} busy={Boolean(busyId)} error={confirmationError} onCancel={() => setConfirmation(null)} onConfirm={confirmDelete} /></div>;
}
