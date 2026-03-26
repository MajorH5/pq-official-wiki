( function () {
	'use strict';

	function getQueryParam( key ) {
		var url = new URL( window.location.href );
		return url.searchParams.get( key );
	}

	function setQueryParam( key, value ) {
		var url = new URL( window.location.href );
		if ( value === null || value === undefined || value === '' ) {
			url.searchParams.delete( key );
		} else {
			url.searchParams.set( key, value );
		}
		window.history.pushState( {}, '', url.toString() );
	}

	function activate( root, panelId ) {
		var tabs = root.querySelectorAll( '.pq-roblox-tab' );
		var panels = root.querySelectorAll( '.pq-roblox-tabpanel' );
		tabs.forEach( function ( btn ) {
			var id = btn.getAttribute( 'data-tab' );
			var on = id === panelId;
			btn.classList.toggle( 'is-active', on );
			btn.setAttribute( 'aria-selected', on ? 'true' : 'false' );
		} );
		panels.forEach( function ( p ) {
			p.hidden = p.id !== panelId;
		} );
	}

	function initTabs() {
		var tabFromUrl = getQueryParam( 'tab' );
		document.querySelectorAll( '.pq-roblox-profile-tabs' ).forEach( function ( root ) {
			var tabs = root.querySelectorAll( '.pq-roblox-tab' );
			if ( !tabs.length ) {
				return;
			}
			tabs.forEach( function ( btn ) {
				btn.addEventListener( 'click', function () {
					var id = btn.getAttribute( 'data-tab' );
					if ( id ) {
						setQueryParam( 'tab', id );
						activate( root, id );
					}
				} );
			} );
			var first = tabs[ 0 ].getAttribute( 'data-tab' );
			if ( first ) {
				// If the URL asks for a tab that's not present, fall back to the first.
				var want = tabFromUrl;
				if ( want ) {
					var panel = root.querySelector( '#' + want );
					if ( panel ) {
						activate( root, want );
						return;
					}
				}
				activate( root, first );
			}
		} );
	}

	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', initTabs );
	} else {
		initTabs();
	}
}() );
