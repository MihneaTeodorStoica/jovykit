# Automation

The repository uses GitHub Actions for:

- Python checks and tests in `.github/workflows/ci.yml`.
- Docker image builds and GHCR publishing in
  `.github/workflows/docker-publish.yml`.
- Security scanning in `.github/workflows/security.yml`.

Dependabot configuration, issue templates, pull request templates, and labeler
configuration live under `.github/`.
