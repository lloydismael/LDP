(() => {
  const nativeSubmit = (form) => HTMLFormElement.prototype.submit.call(form);

  document.querySelectorAll('[data-live-list]').forEach((form) => {
    const input = form.querySelector('[data-live-list-input]');
    const clearButton = form.querySelector('[data-live-list-clear]');
    const suggestions = form.querySelector('[data-live-list-suggestions]');
    const status = form.querySelector('[data-live-list-status]');
    const targetId = form.dataset.resultsTarget;
    const results = document.getElementById(targetId);
    if (!input || !results) return;

    let debounceTimer = null;
    let currentController = null;
    let requestSequence = 0;
    let activeIndex = -1;
    let liveFailed = false;

    const closeSuggestions = () => {
      if (suggestions) suggestions.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      activeIndex = -1;
    };

    const openSuggestions = () => {
      if (!suggestions || !suggestions.children.length || document.activeElement !== input) return;
      suggestions.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    };

    const collectParams = (overrides = {}) => {
      const params = new URLSearchParams(new FormData(form));
      for (const [key, value] of Object.entries(overrides)) {
        if (value === null || value === undefined || value === '') params.delete(key);
        else params.set(key, value);
      }
      return params;
    };

    const createSuggestion = (item, index) => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'activity-suggestion';
      option.id = `${form.id || 'live-list'}-option-${index}`;
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      option.dataset.suggestionValue = item.label;
      const label = document.createElement('span');
      label.className = 'activity-suggestion-name';
      label.textContent = item.label;
      const meta = document.createElement('span');
      meta.className = 'activity-suggestion-school';
      meta.textContent = item.meta || item.school || '';
      option.append(label, meta);
      return option;
    };

    const renderSuggestions = (items, query, shouldOpen) => {
      if (!suggestions) return;
      suggestions.replaceChildren();
      if (query.length < 2) {
        closeSuggestions();
        return;
      }
      if (!items.length) {
        const empty = document.createElement('div');
        empty.className = 'activity-suggestion-empty';
        empty.textContent = 'No matching results.';
        suggestions.appendChild(empty);
      } else {
        items.slice(0, 8).forEach((item, index) => suggestions.appendChild(createSuggestion(item, index)));
      }
      if (shouldOpen) openSuggestions();
    };

    const suggestionsFromFragment = (fragment) => [...fragment.querySelectorAll('[data-suggestion-label]')].slice(0, 8).map((row) => ({
      label: row.dataset.suggestionLabel,
      meta: row.dataset.suggestionMeta || '',
    }));

    const setActiveOption = (nextIndex) => {
      if (!suggestions) return;
      const options = [...suggestions.querySelectorAll('[role="option"]')];
      if (!options.length) return;
      activeIndex = (nextIndex + options.length) % options.length;
      options.forEach((option, index) => {
        const active = index === activeIndex;
        option.classList.toggle('is-active', active);
        option.setAttribute('aria-selected', String(active));
      });
      input.setAttribute('aria-activedescendant', options[activeIndex].id);
      options[activeIndex].scrollIntoView({ block: 'nearest' });
    };

    const updateUrl = (params, mode) => {
      if (mode === 'none') return;
      const url = new URL(form.action || window.location.pathname, window.location.origin);
      url.search = params.toString();
      history[mode === 'push' ? 'pushState' : 'replaceState']({ liveList: true }, '', url);
    };

    const search = async ({ overrides = {}, historyMode = 'replace', showSuggestions = false, focusSelector = null } = {}) => {
      window.clearTimeout(debounceTimer);
      if (currentController) currentController.abort();
      const requestController = new AbortController();
      currentController = requestController;
      const sequence = ++requestSequence;
      const params = collectParams(overrides);
      params.delete('page');
      if (overrides.page) params.set('page', overrides.page);
      form.classList.add('is-loading');
      results.setAttribute('aria-busy', 'true');
      if (status) status.textContent = 'Searching…';

      try {
        const endpoint = form.dataset.endpoint || form.action || window.location.pathname;
        const response = await fetch(`${endpoint}?${params}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, signal: requestController.signal });
        if (!response.ok) throw new Error(`Search failed (${response.status})`);
        const contentType = response.headers.get('content-type') || '';
        let html;
        let count;
        let items = [];
        let query = input.value.trim();
        if (contentType.includes('application/json')) {
          const data = await response.json();
          html = data.html;
          count = data.count;
          query = data.query;
          items = (data.suggestions || []).map((item) => ({ label: item.label, meta: item.school || item.meta || '' }));
        } else {
          const documentResult = new DOMParser().parseFromString(await response.text(), 'text/html');
          const replacement = documentResult.getElementById(targetId);
          if (!replacement) throw new Error('Results fragment was not found.');
          html = replacement.innerHTML;
          const countNode = replacement.matches('[data-live-list-count]')
            ? replacement
            : replacement.querySelector('[data-live-list-count]');
          count = countNode ? Number(countNode.dataset.liveListCount) : replacement.querySelectorAll('[data-suggestion-label]').length;
          items = suggestionsFromFragment(replacement);
        }
        if (sequence !== requestSequence) return;
        results.innerHTML = html;
        renderSuggestions(items, query, showSuggestions);
        if (clearButton) clearButton.classList.toggle('is-hidden', !query);
        if (status) status.textContent = query ? `${count} result${count === 1 ? '' : 's'} found for “${query}”.` : `${count} result${count === 1 ? '' : 's'} available.`;
        updateUrl(params, historyMode);
        liveFailed = false;
        if (focusSelector) results.querySelector(focusSelector)?.focus();
      } catch (error) {
        if (error.name !== 'AbortError') {
          liveFailed = true;
          closeSuggestions();
          if (status) status.textContent = 'Live search is unavailable. Press Enter to load results.';
        }
      } finally {
        if (currentController === requestController) {
          form.classList.remove('is-loading');
          results.setAttribute('aria-busy', 'false');
        }
      }
    };

    input.addEventListener('input', () => {
      window.clearTimeout(debounceTimer);
      if (clearButton) clearButton.classList.toggle('is-hidden', !input.value);
      debounceTimer = window.setTimeout(() => search({ historyMode: 'replace', showSuggestions: true }), Number(form.dataset.debounce || 280));
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') { event.preventDefault(); setActiveOption(activeIndex + 1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); setActiveOption(activeIndex - 1); }
      else if (event.key === 'Escape') { event.preventDefault(); closeSuggestions(); }
      else if (event.key === 'Enter' && activeIndex >= 0 && suggestions) {
        const option = suggestions.querySelectorAll('[role="option"]')[activeIndex];
        if (option) { event.preventDefault(); input.value = option.dataset.suggestionValue; closeSuggestions(); search({ historyMode: 'push' }); }
      }
    });

    clearButton?.addEventListener('click', () => {
      input.value = '';
      clearButton.classList.add('is-hidden');
      closeSuggestions();
      input.focus();
      search({ overrides: { q: null }, historyMode: 'push' });
    });

    suggestions?.addEventListener('click', (event) => {
      const option = event.target.closest('[data-suggestion-value]');
      if (!option) return;
      input.value = option.dataset.suggestionValue;
      closeSuggestions();
      search({ historyMode: 'push' });
    });

    results.addEventListener('click', (event) => {
      const link = event.target.closest('[data-live-sort], [data-live-page]');
      if (!link) return;
      event.preventDefault();
      closeSuggestions();
      const url = new URL(link.href, window.location.origin);
      const overrides = Object.fromEntries(url.searchParams.entries());
      search({ overrides, historyMode: 'push', focusSelector: link.dataset.liveSort ? `[data-live-sort="${link.dataset.liveSort}"]` : null });
    });

    form.addEventListener('submit', (event) => {
      if (!window.fetch || liveFailed) return;
      event.preventDefault();
      closeSuggestions();
      search({ historyMode: 'push' });
    });

    document.addEventListener('click', (event) => { if (!form.contains(event.target)) closeSuggestions(); });
    window.addEventListener('popstate', () => {
      const params = new URLSearchParams(window.location.search);
      [...form.elements].forEach((element) => {
        if (element.name && element.type !== 'submit') element.value = params.get(element.name) || '';
      });
      search({ overrides: Object.fromEntries(params.entries()), historyMode: 'none' });
    });
  });
})();
