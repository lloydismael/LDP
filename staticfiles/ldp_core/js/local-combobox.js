(() => {
  document.querySelectorAll('[data-local-filter]').forEach((input) => {
    const targetSelector = input.dataset.localFilter;
    const rows = [...document.querySelectorAll(targetSelector)];
    input.addEventListener('input', () => {
      const query = input.value.trim().toLowerCase();
      rows.forEach((row) => {
        const searchable = (row.dataset.searchText || row.textContent).toLowerCase();
        row.hidden = query !== '' && !searchable.includes(query);
      });
    });
  });

  document.querySelectorAll('[data-local-multiselect]').forEach((root) => {
    const input = root.querySelector('[data-local-multiselect-input]');
    const list = root.querySelector('[data-local-multiselect-list]');
    const status = root.querySelector('[data-local-multiselect-status]');
    const clear = root.querySelector('[data-local-multiselect-clear]');
    const participantList = document.getElementById('participantList');
    if (!input || !list || !participantList) return;

    const items = [...participantList.querySelectorAll('.participant-row')].map((row) => ({
      id: row.dataset.participantId,
      name: row.dataset.participantName || row.querySelector('.participant-name')?.textContent.trim() || 'Participant',
      meta: row.dataset.participantMeta || '',
      searchText: (row.dataset.searchText || row.textContent).toLowerCase(),
      row,
      checkbox: row.querySelector('input[type="checkbox"]'),
    })).filter((item) => item.id && item.checkbox);
    let matches = items;
    let activeIndex = -1;

    const announce = (message) => { if (status) status.textContent = message; };
    const close = () => {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      activeIndex = -1;
    };
    const setActive = (index) => {
      const options = [...list.querySelectorAll('[role="option"]')];
      if (!options.length) return;
      activeIndex = (index + options.length) % options.length;
      options.forEach((option, optionIndex) => option.classList.toggle('is-active', optionIndex === activeIndex));
      const active = options[activeIndex];
      input.setAttribute('aria-activedescendant', active.id);
      active.scrollIntoView({ block: 'nearest' });
    };
    const syncOption = (item) => {
      const option = list.querySelector(`[data-participant-option="${CSS.escape(item.id)}"]`);
      if (!option) return;
      option.setAttribute('aria-selected', String(item.checkbox.checked));
      option.classList.toggle('is-selected', item.checkbox.checked);
      const indicator = option.querySelector('.participant-suggestion-check');
      if (indicator) indicator.className = `fas ${item.checkbox.checked ? 'fa-check-circle' : 'fa-circle'} participant-suggestion-check`;
    };
    const toggle = (item) => {
      item.checkbox.checked = !item.checkbox.checked;
      item.checkbox.dispatchEvent(new Event('change', { bubbles: true }));
      syncOption(item);
      announce(`${item.name} ${item.checkbox.checked ? 'selected' : 'removed'}.`);
    };
    const render = () => {
      const query = input.value.trim().toLowerCase();
      matches = items.filter((item) => !query || item.searchText.includes(query));
      items.forEach((item) => { item.row.hidden = query !== '' && !item.searchText.includes(query); });
      clear?.classList.toggle('is-hidden', !query);
      list.replaceChildren();
      activeIndex = -1;

      if (!matches.length) {
        const empty = document.createElement('div');
        empty.className = 'activity-suggestion-empty';
        empty.textContent = 'No participants match that search. Try a name, username, or type.';
        list.appendChild(empty);
      } else {
        matches.slice(0, 12).forEach((item) => {
          const option = document.createElement('button');
          option.type = 'button';
          option.id = `participant-option-${item.id}`;
          option.className = 'activity-suggestion participant-suggestion';
          option.dataset.participantOption = item.id;
          option.setAttribute('role', 'option');
          option.setAttribute('aria-selected', String(item.checkbox.checked));
          option.classList.toggle('is-selected', item.checkbox.checked);

          const copy = document.createElement('span');
          copy.className = 'participant-suggestion-copy';
          const name = document.createElement('span');
          name.className = 'activity-suggestion-name';
          name.textContent = item.name;
          const meta = document.createElement('span');
          meta.className = 'activity-suggestion-school';
          meta.textContent = item.meta;
          const indicator = document.createElement('i');
          indicator.className = `fas ${item.checkbox.checked ? 'fa-check-circle' : 'fa-circle'} participant-suggestion-check`;
          indicator.setAttribute('aria-hidden', 'true');
          copy.append(name, meta);
          option.append(copy, indicator);
          option.addEventListener('mousedown', (event) => event.preventDefault());
          option.addEventListener('click', () => toggle(item));
          list.appendChild(option);
        });
      }
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      const suffix = matches.length > 12 ? ', showing the first 12.' : '.';
      announce(`${matches.length} participant${matches.length === 1 ? '' : 's'} found${suffix}`);
    };

    input.addEventListener('focus', render);
    input.addEventListener('input', render);
    input.addEventListener('keydown', (event) => {
      const options = [...list.querySelectorAll('[role="option"]')];
      if (event.key === 'Escape') { event.preventDefault(); close(); return; }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (list.hidden) render();
        setActive(event.key === 'ArrowDown' ? activeIndex + 1 : activeIndex - 1);
      } else if ((event.key === 'Enter' || event.key === ' ') && activeIndex >= 0 && options[activeIndex]) {
        event.preventDefault();
        const item = items.find((candidate) => candidate.id === options[activeIndex].dataset.participantOption);
        if (item) toggle(item);
      }
    });
    clear?.addEventListener('click', () => {
      input.value = '';
      render();
      input.focus();
    });
    items.forEach((item) => item.checkbox.addEventListener('change', () => syncOption(item)));
    document.addEventListener('click', (event) => { if (!root.contains(event.target)) close(); });
  });

  document.querySelectorAll('[data-local-combobox]').forEach((root) => {
    const input = root.querySelector('[data-local-combobox-input]');
    const value = root.querySelector('[data-local-combobox-value]');
    const list = root.querySelector('[data-local-combobox-list]');
    const source = root.querySelector('script[type="application/json"]')
      || (root.dataset.source ? document.getElementById(root.dataset.source) : null);
    const clear = root.querySelector('[data-local-combobox-clear]');
    const status = root.querySelector('[data-local-combobox-status]');
    if (!input || !value || !list || !source) return;
    const options = JSON.parse(source.textContent);
    let activeIndex = -1;

    const close = () => {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      activeIndex = -1;
    };

    const choose = (option) => {
      input.value = option.l;
      value.value = option.v;
      clear?.classList.remove('is-hidden');
      close();
      root.dispatchEvent(new CustomEvent('local-combobox-change', { bubbles: true, detail: option }));
      if (status) status.textContent = `${option.l} selected.`;
    };

    const render = () => {
      const query = input.value.trim().toLowerCase();
      const matches = options.filter((option) => option.l.toLowerCase().includes(query)).slice(0, 20);
      list.replaceChildren();
      if (!matches.length) {
        const empty = document.createElement('div');
        empty.className = 'activity-suggestion-empty';
        empty.textContent = 'No matches found.';
        list.appendChild(empty);
      } else {
        matches.forEach((option, index) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'activity-suggestion';
          button.id = `${input.id || 'local-combobox'}-option-${index}`;
          button.setAttribute('role', 'option');
          button.setAttribute('aria-selected', 'false');
          button.textContent = option.l;
          button.addEventListener('mousedown', (event) => { event.preventDefault(); choose(option); });
          list.appendChild(button);
        });
      }
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      if (status) {
        const total = options.filter((option) => option.l.toLowerCase().includes(query)).length;
        const suffix = total > 20 ? ', showing the first 20.' : '.';
        status.textContent = `${total} school${total === 1 ? '' : 's'} found${suffix}`;
      }
    };

    const initial = options.find((option) => String(option.v) === String(value.value));
    if (initial && !input.value) input.value = initial.l;
    input.addEventListener('focus', render);
    input.addEventListener('input', () => { value.value = ''; render(); });
    input.addEventListener('keydown', (event) => {
      const rendered = [...list.querySelectorAll('[role="option"]')];
      if (event.key === 'Escape') { event.preventDefault(); close(); return; }
      if (!rendered.length) return;
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        activeIndex = event.key === 'ArrowDown' ? (activeIndex + 1) % rendered.length : (activeIndex - 1 + rendered.length) % rendered.length;
        rendered.forEach((option, index) => {
          const active = index === activeIndex;
          option.classList.toggle('is-active', active);
          option.setAttribute('aria-selected', String(active));
        });
        input.setAttribute('aria-activedescendant', rendered[activeIndex].id);
      } else if (event.key === 'Enter' && activeIndex >= 0) {
        event.preventDefault();
        const match = options.find((option) => option.l === rendered[activeIndex].textContent);
        if (match) choose(match);
      }
    });
    clear?.addEventListener('click', () => {
      input.value = '';
      value.value = '';
      clear.classList.add('is-hidden');
      input.focus();
      root.dispatchEvent(new CustomEvent('local-combobox-change', { bubbles: true, detail: null }));
    });
    input.addEventListener('blur', () => window.setTimeout(() => { if (!value.value) input.value = ''; close(); }, 120));
  });
})();
