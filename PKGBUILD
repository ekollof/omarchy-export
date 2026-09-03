pkgname=omarchy-export
pkgver=1.0.0
pkgrel=1
pkgdesc="Export and import transportable Omarchy settings bundles"
arch=(any)
url="https://github.com/ekollof/omarchy-export"
license=(MIT)
depends=(python)
optdepends=("fzf: interactive category picker" "git: plugin and devlink export fidelity")
source=("$pkgname::git+$url.git#tag=v$pkgver")
sha256sums=(SKIP)

package() {
  local libdir="$pkgdir/usr/lib/omarchy-export"
  install -d "$libdir" "$pkgdir/usr/bin"
  cp -r "$srcdir/$pkgname/omarchy_export" "$libdir/"
  install -m 755 "$srcdir/$pkgname/bin/omarchy-export" "$pkgdir/usr/bin/omarchy-export"
  install -Dm 644 "$srcdir/$pkgname/README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
  install -Dm 644 "$srcdir/$pkgname/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
