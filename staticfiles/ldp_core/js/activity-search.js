(() => {
  const form = document.querySelector('[data-activity-search]');
  if (!form) return;

  const input = form.querySelector('[data-activity-search-input]');
  const clearButton = form.querySelector('[data-activity-search-clear]');
  const suggestions = form.querySelector('[data-activity-suggestions]');
  const status = form.querySelector('[data-activity-search-status]');
  const sortInput = form.querySelector('[data-activity-sort]');
  const directionInput = form.querySelector('[data-activity-direction]');
  const results = document.querySelector('[data-activity-results]');
  const endpoint = form.dataset.endpoint;
  let timer;
  let controller;
  let activeIndex = -1;

  const setExpanded = (expanded) => {
    input.setAttribute('aria-expanded', String(expanded));
    suggestions.hidden = !expanded;
    if (!expanded) activeIndex = -1;
  };

  const escapeHtml = (value) => {
    const node = document.createElement('span');
    node.textContent = value;
    return node.innerHTML;
  };

  const renderSuggestions = (items, query) => {
    suggestions.innerHTML = '';
    if (query.length < 2) {
      setExpanded(false);
      return;
    }
    if (!items.length) {
      suggestions.innerHTML = '<div class="activity-suggestion-empty">No matching activities.</div>';
      setExpanded(true);
      return;
    }
    suggestions.innerHTML = items.map((item, index) => (
      `<button type="button" class="activity-suggestion" role="option" id="activity-suggestion-${index}" data-suggestion-index="${index}" data-suggestion-value="${escapeHtml(item.label)}">` +
      `<span class="activity-suggestion-name">${escapeHtml(item.label)}</span>` +
      `<span class="activity-suggestion-school">${escapeHtml(item.school)}</span></button>`
    )).join('');
    setExpanded(true);
  };

  const updateActiveSuggestion = (nextIndex) => {
    const options = [...suggestions.querySelectorAll('[role="option"]')];
    if (!options.length) return;
    activeIndex = (nextIndex + options.length) % options.length;
    options.forEach((option, index) => option.classList.toggle('is-active', index === activeIndex));
    input.setAttribute('aria-activedescendant', options[activeIndex].id);
    options[activeIndex].scrollIntoView({ block: 'nearest' });
  };

  const buildParams = (overrides = {}) => {
    const params = new URLSearchParams();
    const query = overrides.q ?? input.value.trim();
    if (query) params.set('q', query);
    params.set('sort', overrides.sort ?? sortInput.value);
    params.set('dir', overrides.dir ?? directionInput.value);
    if (overrides.page) params.set('page', overrides.page);
    return params;
  };

  const updateBrowserUrl = (params) => {
    const url = new URL(window.location.href);
    url.search = params.toString();
    history.replaceState({ activitySearch: true }, '', url);
  };

  const performSearch = async (overrides = {}) => {
    window.clearTimeout(timer);
    if (controller) controller.abort();
    controller = new AbortController();
    const params = buildParams(overrides);
    form.classList.add('is-loading');
    results.setAttribute('aria-busy', 'true');
    status.textContent = 'Searching activities…';

    try {
      const response = await fetch(`${endpoint}?${params}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Search failed (${response.status})`);
      const data = await response.json();
      results.innerHTML = data.html;
      renderSuggestions(data.suggestions, data.query);
      clearButton.classList.toggle('is-hidden', !data.query);
      status.textContent = data.query
        ? `${data.count} ${data.count === 1 ? 'activity' : 'activities'} found for “${data.query}”.`
        : `${data.count} ${data.count === 1 ? 'activity' : 'activities'} available.`;
      updateBrowserUrl(params);
    } catch (error) {
      if (error.name !== 'AbortError') {
        status.textContent = 'Live search is unavailable. Press Enter or Search to continue.';
        setExpanded(false);
      }
    } finally {
      if (!controller.signal.aborted) {
        form.classList.remove('is-loading');
        results.setAttribute('aria-busy', 'false');
      }
    }
  };

  input.addEventListener('input', () => {
    clearButton.classList.toggle('is-hidden', !input.value);
    timer = window.setTimeout(() => performSearch(), 280);
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      updateActiveSuggestion(activeIndex + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      updateActiveSuggestion(activeIndex - 1);
    } else if (event.key === 'Escape') {
      setExpanded(false);
      input.removeAttribute('aria-activedescendant');
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      const option = suggestions.querySelectorAll('[role="option"]')[activeIndex];
      if (option) {
        event.preventDefault();
        input.value = option.dataset.suggestionValue;
        setExpanded(false);
        performSearch();
      }
    }
  });

  clearButton.addEventListener('click', () => {
    input.value = '';
    clearButton.classList.add('is-hidden');
    setExpanded(false);
    input.focus();
    performSearch({ q: '' });
  });

  suggestions.addEventListener('click', (event) => {
    const option = event.target.closest('[data-suggestion-value]');
    if (!option) return;
    input.value = option.dataset.suggestionValue;
    setExpanded(false);
    performSearch();
  });

  results.addEventListener('click', (event) => {
    const sortButton = event.target.closest('[data-sort]');
    if (sortButton) {
      const field = sortButton.dataset.sort;
      directionInput.value = sortInput.value === field && directionInput.value === 'asc' ? 'desc' : 'asc';
      sortInput.value = field;
      performSearch({ sort: field, dir: directionInput.value });
      return;
    }
    const pageLink = event.target.closest('a[href*="page="]');
    if (pageLink) {
      event.preventDefault();
      const url = new URL(pageLink.href);
      performSearch({ page: url.searchParams.get('page') });
    }
  });

  form.addEventListener('submit', (event) => {
    if (!window.fetch) return;
    event.preventDefault();
    setExpanded(false);
    performSearch();
  });

  document.addEventListener('click', (event) => {
    if (!form.contains(event.target)) setExpanded(false);
  });

  window.addEventListener('popstate', () => {
    const params = new URLSearchParams(window.location.search);
    input.value = params.get('q') || '';
    sortInput.value = params.get('sort') || 'date';
    directionInput.value = params.get('dir') || 'desc';
    performSearch({ q: input.value, page: params.get('page') });
  });
})();
