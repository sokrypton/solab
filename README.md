# solab.org

Static website for the Ovchinnikov Lab (solab), MIT Biology. Plain HTML + one
CSS file, no build step. A faithful recreation of the original Google Sites
design (steel-blue header, white wordmark, MIT footer).

## Structure

```
index.html              Home (hero + News)
home/                    Redirect → index.html (preserves the old /home URL)
lab/index.html           Current members
lab/alumni/index.html    Alumni
lab/join/index.html      How to join
research/index.html      Research themes
publications/index.html  Full publication list
tools/index.html         Software
resources/index.html     Learning resources
resources/coevolution-structure-prediction/  Coevolution milestones timeline
contact/index.html       Contact
assets/css/style.css     All styling (design tokens at the top)
assets/img/hero.png      Homepage hero graphic
404.html                 Not-found page (served by GitHub Pages)
```

Every page uses **document-relative links** (`../research/index.html`, not
`/research/`), so the site works three ways:

- opened directly from disk in a browser (`file://`),
- served from a subpath (e.g. `username.github.io/solab/`),
- served from the domain root (`solab.org`, where typing `/research` still resolves).

## Adding a news item

Edit `index.html`, and add a `<li>` at the top of the `.news` list:

```html
<li>
  <span class="date">Aug 2026</span>
  Your update here, with <a href="https://example.com">links</a>.
</li>
```

## Adding a lab member

Copy a `.person` card in `lab/index.html` and edit the initials, name, and role:

```html
<div class="person">
  <div class="avatar">AB</div>
  <div class="name">Ada Byron</div>
  <div class="role">PostDoc</div>
  <div class="links"><a href="https://x.com/handle">@handle</a></div>
</div>
```

To use a real photo instead of initials, replace the `.avatar` div with
`<img class="avatar" src="../assets/img/people/ada.jpg" alt="Ada Byron">`.

### Member photos

Photos in `assets/img/people/<slug>.jpg` are the real photos from the live
solab.org (Google Sites) pages — all current members, virtual members, and all
25 alumni. Research theme illustrations are in `assets/img/research/`.
To add a new member photo, drop `<slug>.jpg` into `assets/img/people/` and use
`<img class="avatar" src="../assets/img/people/<slug>.jpg" alt="Name">`.

## Deploying on GitHub Pages

1. Push this folder to a GitHub repo.
2. Settings → Pages → deploy from the `main` branch, root.
3. (Optional) For the custom domain, keep `CNAME`, point `solab.org` DNS at
   GitHub Pages, and enable "Enforce HTTPS".

`.nojekyll` tells Pages to serve the files as-is (no Jekyll processing).
