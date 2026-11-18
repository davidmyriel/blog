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
`config.json`: name, tagline, social links, form endpoints, and the Projects list on the homepage.

## Contact form (keeps your email private)
Your email address is never written on the site. The Work with me and Newsletter forms post to a form service that forwards messages to your inbox.
1. Sign up free at formspree.io and create a form (it asks for the email to deliver to; that stays private on Formspree).
2. Copy the form's endpoint, e.g. `https://formspree.io/f/abcdwxyz`, into `contact_form_endpoint` in `config.json`.
3. Rebuild and push. Until this is set, the forms show "This form is not connected yet."
To use a separate list for the newsletter (Buttondown, Substack), put its form URL in `newsletter_form_action`.
