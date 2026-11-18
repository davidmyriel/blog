# Site source

The homepage, Work with me, Newsletter, About and blog posts are generated from this folder.
Older projects live in `/topk/` and are not touched by the build.

## Write a post
1. Copy `posts/_TEMPLATE.md` to `posts/my-post.md` (URL becomes `/posts/my-post/`).
2. Write it in Markdown. Change `draft: true` to `draft: false` when it's ready.

## Build (from the repo root)
    pip install markdown
    python3 _source/build.py            # published posts only
    python3 _source/build.py --drafts   # preview drafts too (don't commit this build)
    python3 -m http.server 8000         # open http://localhost:8000

Then commit and push. The generated files sit at the repo root so the site is served as-is.

## Settings
`config.json`: name, tagline, social links, contact link, and the Projects list on the homepage.

## Contact
There is no form and no email on the site. "Get in touch" links go to `contact_url` in `config.json` (your LinkedIn).
