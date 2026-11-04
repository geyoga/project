(() => {
  let bookmarks = new Set();
  const id = apartment => String(apartment.listing_id);
  const icon = apartment => `<button class="bookmark-button${bookmarks.has(id(apartment)) ? ' active' : ''}" type="button" data-bookmark="${id(apartment)}" aria-label="${bookmarks.has(id(apartment)) ? 'Remove apartment bookmark' : 'Bookmark apartment'}" aria-pressed="${bookmarks.has(id(apartment))}">★</button>`;
  const save = async () => {
    const response = await fetch('/bookmarks.json', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({bookmarks:[...bookmarks]})});
    if (!response.ok) throw new Error('Could not save bookmark');
  };
  window.apartmentBookmarks = {has: apartment => bookmarks.has(id(apartment)), icon};
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
    window.dispatchEvent(new CustomEvent('bookmarks-ready')); window.render?.();
  });
})();
