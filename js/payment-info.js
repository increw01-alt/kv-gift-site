'use strict';
(() => {
  const form = document.getElementById('cost-form');
  const ids = ['purchase', 'fee', 'interest'];
  const money = new Intl.NumberFormat('ko-KR');
  const amountLimit = 1_000_000_000;
  const fields = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
  const result = document.querySelector('.cost-result');
  const resultLabel = document.getElementById('result-label');
  const resultTotal = document.getElementById('result-total');
  const resultMessage = document.getElementById('result-message');
  const exampleNote = document.getElementById('example-note');
  let resultVisible = false;
  let exampleMode = false;

  function parseAmount(raw) {
    if (raw.trim() === '') return null;
    // Accept ungrouped digits or correctly grouped whole won amounts only.
    if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(raw.trim())) return NaN;
    const value = Number(raw.trim().replaceAll(',', ''));
    return Number.isSafeInteger(value) && value <= amountLimit ? value : NaN;
  }
  function setError(id, message) {
    const error = document.getElementById(`${id}-error`);
    error.textContent = message;
    error.hidden = !message;
    fields[id].setAttribute('aria-invalid', String(Boolean(message)));
  }
  function clearResult() {
    result.classList.remove('has-value');
    resultLabel.textContent = '입력한 비용 합계';
    resultTotal.textContent = '금액을 입력해 주세요';
    resultMessage.textContent = '확인된 비용을 모아 결제 전 부담액을 살펴보세요.';
    document.getElementById('result-purchase').textContent = '—';
    document.getElementById('result-fee').textContent = '확인 필요';
    document.getElementById('result-interest').textContent = '확인 필요';
  }
  function calculate(focusError) {
    const values = {};
    const invalid = [];
    ids.forEach(id => {
      const value = parseAmount(fields[id].value);
      values[id] = value;
      let message = '';
      if (id === 'purchase' && (value === null || value === 0)) message = '구매 결제금액을 1원 이상 입력해 주세요.';
      else if (Number.isNaN(value)) message = '0~10억 원 사이의 금액을 정수로 입력해 주세요.';
      setError(id, message);
      if (message) invalid.push(id);
    });
    if (invalid.length) {
      clearResult();
      resultTotal.textContent = '입력값을 확인해 주세요';
      resultMessage.textContent = '표시된 항목을 수정하면 다시 계산할 수 있습니다.';
      if (focusError) fields[invalid[0]].focus();
      return false;
    }
    const missing = ['fee', 'interest'].filter(id => values[id] === null);
    const total = ids.reduce((sum, id) => sum + (values[id] ?? 0), 0);
    result.classList.add('has-value');
    resultLabel.textContent = `${exampleMode ? '예시 · ' : ''}${missing.length ? '입력한 비용 소계' : '입력한 비용 합계'}`;
    resultTotal.textContent = `${money.format(total)}원`;
    resultMessage.textContent = missing.length
      ? `미확인 ${missing.length}개 항목은 포함하지 않았습니다. 실제 부담액은 달라질 수 있습니다.`
      : '입력한 금액을 합산했습니다. 실제 청구 조건은 구매처·카드사에서 확인하세요.';
    ids.forEach(id => {
      document.getElementById(`result-${id}`).textContent = values[id] === null ? '확인 필요' : `${money.format(values[id])}원`;
    });
    return true;
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    resultVisible = true;
    calculate(true);
  });
  ids.forEach(id => {
    fields[id].addEventListener('input', () => {
      exampleMode = false;
      exampleNote.hidden = true;
      if (resultVisible) calculate(false);
      else setError(id, '');
    });
    fields[id].addEventListener('blur', () => {
      const value = parseAmount(fields[id].value);
      if (value !== null && !Number.isNaN(value)) fields[id].value = money.format(value);
    });
  });
  document.getElementById('example-button').addEventListener('click', () => {
    fields.purchase.value = '500,000';
    fields.fee.value = '5,000';
    fields.interest.value = '12,000';
    exampleMode = true;
    resultVisible = true;
    exampleNote.hidden = false;
    calculate(false);
  });
  form.addEventListener('reset', () => {
    resultVisible = false;
    exampleMode = false;
    exampleNote.hidden = true;
    ids.forEach(id => setError(id, ''));
    clearResult();
  });
  const issuer = document.getElementById('issuer');
  const condition = document.getElementById('condition-filter');
  const issuance = document.getElementById('issuance-filter');
  const search = document.getElementById('card-search');
  const filterReset = document.getElementById('filter-reset');
  const normalize = value => value.normalize('NFKC').toLocaleLowerCase('ko-KR').trim();
  issuance.value = 'application_open';
  [issuer, condition, issuance, search, filterReset].forEach(control => { control.disabled = false; });
  function filterCards() {
    const words = normalize(search.value).split(/\s+/).filter(Boolean);
    let count = 0;
    document.querySelectorAll('[data-issuer]').forEach(row => {
      const matchesIssuer = issuer.value === 'all' || row.dataset.issuer === issuer.value;
      const matchesCondition = condition.value === 'all' || row.dataset.condition === condition.value;
      const matchesIssuance = issuance.value === 'all' || row.dataset.issuance === issuance.value;
      const haystack = normalize(row.dataset.search || row.textContent);
      row.hidden = !matchesIssuer || !matchesCondition || !matchesIssuance || !words.every(word => haystack.includes(word));
      if (!row.hidden) count++;
    });
    document.getElementById('filter-status').textContent = `${count}종 표시 · 발급 추천 순위가 아닌 조건 확인용 자료입니다.`;
    document.getElementById('filter-empty').hidden = count !== 0;
  }
  issuer.addEventListener('change', filterCards);
  condition.addEventListener('change', filterCards);
  issuance.addEventListener('change', filterCards);
  search.addEventListener('input', filterCards);
  filterReset.addEventListener('click', () => {
    issuer.value = 'all';
    condition.value = 'all';
    issuance.value = 'all';
    search.value = '';
    filterCards();
    search.focus();
  });
  filterCards();
  document.querySelectorAll('[data-card-terms]').forEach(link => link.addEventListener('click', event => {
    const target = document.getElementById('terms-' + link.dataset.cardTerms);
    if (!target) return;
    event.preventDefault();
    target.closest('details').open = true;
    target.focus();
    target.scrollIntoView({block: 'start'});
  }));
  const checks = [...document.querySelectorAll('.check-item input')];
  checks.forEach(input => input.addEventListener('change', () => {
    const checked = checks.filter(item => item.checked).length;
    document.getElementById('check-count').textContent = `${checked} / ${checks.length} 확인${checked === checks.length ? ' 완료' : ''}`;
    document.getElementById('check-progress').value = checked;
  }));
  // Consultation links retain the existing site's Channel Talk URL and tel:
  // format so the existing GTM click rules can continue to match them.
})();
