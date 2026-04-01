/**
 * First-visit cookie consent for Google Analytics (GTag). Sets pq_cookie_consent and reloads.
 */
(function () {
	function pqSetCookie(name, value, maxAgeSec) {
		var secure = window.location.protocol === 'https:' ? '; Secure' : '';
		document.cookie = name + '=' + encodeURIComponent(value) +
			'; Path=/; Max-Age=' + String(maxAgeSec) + '; SameSite=Lax' + secure;
	}

	function pqBuild() {
		if (!window.mw || !mw.message) {
			return;
		}
		if (document.getElementById('pq-cookieconsent')) {
			return;
		}
		var wrap = document.createElement('div');
		wrap.id = 'pq-cookieconsent';
		wrap.className = 'pq-cookieconsent';
		wrap.setAttribute('role', 'dialog');
		wrap.setAttribute('aria-live', 'polite');

		var inner = document.createElement('div');
		inner.className = 'pq-cookieconsent-inner';

		var text = document.createElement('p');
		text.className = 'pq-cookieconsent-text';
		text.textContent = mw.message('pqroblox-cookieconsent-text').text();

		var actions = document.createElement('div');
		actions.className = 'pq-cookieconsent-actions';

		var accept = document.createElement('button');
		accept.type = 'button';
		accept.className = 'pq-cookieconsent-btn pq-cookieconsent-btn-accept';
		accept.textContent = mw.message('pqroblox-cookieconsent-accept').text();
		accept.addEventListener('click', function () {
			pqSetCookie('pq_cookie_consent', '1', 365 * 24 * 60 * 60);
			window.location.reload();
		});

		var reject = document.createElement('button');
		reject.type = 'button';
		reject.className = 'pq-cookieconsent-btn pq-cookieconsent-btn-reject';
		reject.textContent = mw.message('pqroblox-cookieconsent-reject').text();
		reject.addEventListener('click', function () {
			pqSetCookie('pq_cookie_consent', '0', 365 * 24 * 60 * 60);
			window.location.reload();
		});

		actions.appendChild(accept);
		actions.appendChild(reject);

		inner.appendChild(text);
		inner.appendChild(actions);

		var policyPlain = mw.message('pqroblox-cookieconsent-policy').plain();
		if (policyPlain && policyPlain.trim() !== '') {
			var p = document.createElement('div');
			p.className = 'pq-cookieconsent-policy';
			p.innerHTML = mw.message('pqroblox-cookieconsent-policy').parse();
			inner.appendChild(p);
		}

		wrap.appendChild(inner);
		document.body.appendChild(wrap);
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', pqBuild);
	} else {
		pqBuild();
	}
})();
