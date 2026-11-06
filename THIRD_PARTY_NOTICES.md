# Third-party materials

Aegis-owned code and documentation use [Apache-2.0](LICENSE). This does not relicense dependencies, reference works or the vendored template.

## Source template

`examples/external_react_agent/upstream/` contains selected unmodified files from [langchain-ai/react-agent](https://github.com/langchain-ai/react-agent/tree/9e516c6d8d4f2025949ad9279c4af147eab0683e), revision `9e516c6d8d4f2025949ad9279c4af147eab0683e`. Its original [MIT license](examples/external_react_agent/upstream/LICENSE) is retained. [upstream.json](examples/external_react_agent/upstream.json) records every copied path and SHA-256. The runner copies files to local output and explicitly changes two service seams; the upstream source here stays unchanged.

## Dashboard distribution

The [full dependency license/NOTICE texts](dashboard/public/third-party-notices.txt) accompany the browser distribution at `/third-party-notices.txt`. They cover the locked npm production dependency closure, including Vue, Apache ECharts, zrender, lossless-json, tslib and build-time subdependencies in that closure. ECharts NOTICE and its embedded d3 license are included. This conservative closure may include modules not present in the optimized bundle.

After `npm --prefix dashboard ci`, reproduce with `python scripts/third_party_notices.py`; verify with `--check`. CI rejects drift. The original package authors retain their copyrights and license terms; our Apache license does not replace them.

## Python, containers and references

Python dependencies are installed separately according to [requirements-dev.lock](requirements-dev.lock) and component metadata. Their installed distributions retain their own licenses and metadata; the Collector container retains those installed distributions. Base images retain their upstream distribution notices. SDK/Runtime/Policy/Collector wheels include Aegis LICENSE and NOTICE; this repository does not vendor Python dependency source archives.

[resources](resources/README.md) holds source links, version/hash metadata and original research notes, not complete third-party articles or sites. Public product UI was informed by the cited interface patterns; no third-party UI implementation, logos or artwork was copied. Documentation citations do not imply endorsement.
