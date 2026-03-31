# Pixel Quest wiki — extend official MediaWiki image with bundled extensions.
# Build context: ./mediawiki (see docker-compose.yml).

FROM alpine:3.20 AS embedvideo-src
RUN apk add --no-cache git ca-certificates \
	&& git clone --depth 1 https://github.com/StarCitizenWiki/mediawiki-extensions-EmbedVideo.git /EmbedVideo

FROM mediawiki:lts

# Optional extensions (match your MediaWiki branch when pinning; adjust REL branch if install fails)
RUN git clone --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/Lingo.git /var/www/html/extensions/Lingo \
	&& git clone --depth 1 https://github.com/wikimedia/mediawiki-extensions-WikiSEO.git /var/www/html/extensions/WikiSEO

COPY --from=embedvideo-src --chown=www-data:www-data /EmbedVideo /var/www/html/extensions/EmbedVideo

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
