<?php
/**
 * PixelQuestRoblox extension — loaded from LocalSettings.php via:
 *   require_once __DIR__ . '/LocalSettings.pixelquest-snippet.php';
 * (docker-compose mounts this file next to LocalSettings.php in the container.)
 */
wfLoadExtension( 'PixelQuestRoblox' );

// --- Revision suppression / RevisionDelete permissions (MediaWiki core) ---
// MediaWiki includes Special:RevisionDelete / revision suppression in core (no extra extension needed).
// You just need the right permissions enabled for the groups you want to use it.
$wgGroupPermissions['sysop']['deleterevision'] = true;     // hide revisions from regular users
$wgGroupPermissions['sysop']['suppressrevision'] = true;  // hide from sysops too
$wgGroupPermissions['sysop']['deletedhistory'] = true;   // view deleted history
$wgGroupPermissions['sysop']['deletedtext'] = true;       // view suppressed deleted text
$wgGroupPermissions['sysop']['viewsuppressed'] = true;   // view suppressed content where applicable

// --- MobileFrontend (mobile view / Minerva skin) ---
// Extension files are baked into the Docker image (mediawiki/Dockerfile stage); just load it here.
wfLoadExtension( 'MobileFrontend' );
// Auto-detect mobile devices and show the mobile view.
$wgMFAutodetectMobileView = true;
// Use MinervaNeue as the mobile skin class (already loaded in LocalSettings.php).
$wgMFDefaultSkinClass = 'SkinMinerva';

