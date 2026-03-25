FROM mediawiki:latest

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Extension:Lockdown (match MediaWiki branch in image; see https://www.mediawiki.org/wiki/Extension:Lockdown)
RUN git clone --depth 1 https://github.com/wikimedia/mediawiki-extensions-Lockdown.git /var/www/html/extensions/Lockdown

# Extension:Lingo (glossary hover tooltips)
RUN git clone --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/Lingo.git /var/www/html/extensions/Lingo

# ParserFunctions (#if, #ifeq, …) — required for PQ layout templates
# RUN git clone --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/ParserFunctions.git /var/www/html/extensions/ParserFunctions

RUN a2enmod rewrite

# Allow .htaccess in docroot (official image may use AllowOverride None)
RUN printf '%s\n' \
  '<Directory /var/www/html/>' \
  '    AllowOverride All' \
  '</Directory>' \
  > /etc/apache2/conf-available/pq-wiki-htaccess.conf \
  && a2enconf pq-wiki-htaccess

COPY .htaccess /var/www/html/.htaccess
