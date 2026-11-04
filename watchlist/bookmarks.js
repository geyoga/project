(() => {
  let bookmarks = new Set(), ready = false;
  const id = apartment => String(apartment.listing_id);
  const icon = apartment => `<button class="bookmark-button${bookmarks.has(id(apartment)) ? ' active' : ''}" type="button" data-bookmark="${id(apartment)}" aria-label="${bookmarks.has(id(apartment)) ? 'Remove apartment bookmark' : 'Bookmark apartment'}" aria-pressed="${bookmarks.has(id(apartment))}"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 3.75A1.75 1.75 0 0 1 7.75 2h8.5A1.75 1.75 0 0 1 18 3.75v17.1a.65.65 0 0 1-1.04.52L12 17.5l-4.96 3.87A.65.65 0 0 1 6 20.85V3.75Z"/></svg></button>`;
  const save = async () => {
    const response = await fetch('/bookmarks.json', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({bookmarks:[...bookmarks]})});
    if (!response.ok) throw new Error('Could not save bookmark');
  };
  window.apartmentBookmarks = {has: apartment => bookmarks.has(id(apartment)), ready: () => ready, icon};
  window.addEventListener('click', async event => {
    const button = event.target.closest('[data-bookmark]');
    if (!button) return;
    event.preventDefault(); event.stopPropagation();
    const key = button.dataset.bookmark;
    bookmarks.has(key) ? bookmarks.delete(key) : bookmarks.add(key);
    window.dispatchEvent(new CustomEvent('bookmarks-changed')); window.render?.();
    try { await save(); } catch (error) { bookmarks.has(key) ? bookmarks.delete(key) : bookmarks.add(key); window.dispatchEvent(new CustomEvent('bookmarks-changed')); window.render?.(); alert(error.message); }
  });
  fetch('/bookmarks.json', {cache:'no-store'}).then(response => response.json()).then(data => {
    const available = new Set(apartments.map(id));
    bookmarks = new Set((data.bookmarks || []).filter(key => available.has(key)));
    if (bookmarks.size !== (data.bookmarks || []).length) save();
    ready = true;
    window.dispatchEvent(new CustomEvent('bookmarks-ready')); window.render?.();
  });
})();
