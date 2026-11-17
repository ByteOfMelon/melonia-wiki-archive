# Melonia Civic Society wiki archive

Static, read-only snapshot of the DokuWiki at **melonia-wiki.osolia.xyz** ("Melonia Civic Society"),
served by GitHub Pages from `docs/` at https://melonia-wiki.osolia.xyz.

Every public page is included as DokuWiki rendered it, with the `mikio` theme's styles and the
media those pages use. Editing, page history, search and the site index are not included.
The full `data/` folder (pages, media, attic) is kept privately.

Made with `tools/crawl_dokuwiki.py` against `php -S` using `tools/dw-router.php`:

```
php -S 127.0.0.1:8090 -t /var/www/dokuwiki dw-router.php &
python3 crawl_dokuwiki.py http://127.0.0.1:8090 /var/www/dokuwiki/data/pages ./docs \
        "Melonia Civic Society" melonia-wiki.osolia.xyz
```
