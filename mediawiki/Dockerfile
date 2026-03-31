# Pixel Quest wiki — extend official MediaWiki image with bundled extensions.
# Build context: ./mediawiki (see docker-compose.yml).
#
# All third-party extensions are cloned in an Alpine stage (git is not installed in mediawiki:lts).
# Match mediawiki:lts (1.43.x): use REL1_43 for Wikimedia extensions. EmbedVideo: same clone as manual install.
# After changing this file: docker compose build --no-cache mediawiki

FROM alpine:3.20 AS ext-src
RUN apk add --no-cache git ca-certificates \
	&& set -eu \
	&& git clone --depth 1 https://github.com/StarCitizenWiki/mediawiki-extensions-EmbedVideo.git /EmbedVideo \
	&& test -f /EmbedVideo/extension.json \
	&& git clone --depth 1 -b REL1_43 https://github.com/wikimedia/mediawiki-extensions-Lingo.git /Lingo \
	&& test -f /Lingo/extension.json \
	&& git clone --depth 1 -b REL1_43 https://github.com/wikimedia/mediawiki-extensions-WikiSEO.git /WikiSEO \
	&& test -f /WikiSEO/extension.json \
	&& git clone --depth 1 -b REL1_43 https://github.com/wikimedia/mediawiki-extensions-CheckUser.git /CheckUser \
	&& test -f /CheckUser/extension.json

FROM mediawiki:lts

COPY --from=ext-src --chown=www-data:www-data /EmbedVideo /var/www/html/extensions/EmbedVideo
COPY --from=ext-src --chown=www-data:www-data /Lingo /var/www/html/extensions/Lingo
COPY --from=ext-src --chown=www-data:www-data /WikiSEO /var/www/html/extensions/WikiSEO
COPY --from=ext-src --chown=www-data:www-data /CheckUser /var/www/html/extensions/CheckUser

# Fail the build if copies are missing (catches bad cache / broken COPY)
RUN test -f /var/www/html/extensions/EmbedVideo/extension.json \
	&& test -f /var/www/html/extensions/Lingo/extension.json \
	&& test -f /var/www/html/extensions/WikiSEO/extension.json \
	&& test -f /var/www/html/extensions/CheckUser/extension.json

# CheckUser depends on Composer packages (vendor/ is not committed).
RUN apt-get update \
	&& apt-get install -y --no-install-recommends composer \
	&& cd /var/www/html/extensions/CheckUser && composer install --no-dev --optimize-autoloader \
	&& chown -R www-data:www-data /var/www/html/extensions/CheckUser \
	&& apt-get purge -y composer \
	&& apt-get autoremove -y \
	&& rm -rf /var/lib/apt/lists/*

# Pixel Quest: Roblox linking + profiles (from this repo)
COPY extensions/PixelQuestRoblox /var/www/html/extensions/PixelQuestRoblox

RUN a2enmod rewrite

# Allow .htaccess in docroot (official image may use AllowOverride None)
# Allow .htaccess; deny installer at server level even if rewrite is off.
RUN printf '%s\n' \
	'<Directory /var/www/html/>' \
	'    AllowOverride All' \
	'</Directory>' \
	'<Directory /var/www/html/mw-config>' \
	'    Require all denied' \
	'</Directory>' \
	> /etc/apache2/conf-available/pq-wiki-htaccess.conf \
	&& a2enconf pq-wiki-htaccess

COPY .htaccess /var/www/html/.htaccess
