%global commit e169694390548dfd38ff40f1ef2163d6c3ffe3ea
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global debug_package %{nil}

Name:           aylurs-gtk-shell
Version:        3.1.1
Release:        %autorelease
Summary:        Building blocks for creating custom desktop shells
License:        LGPL-2.1-only
URL:            https://github.com/Aylur/ags
Source0:        %{url}/archive/%{commit}/%{name}-%{version}-%{shortcommit}.tar.gz

BuildRequires:  npm
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  golang
BuildRequires:  gobject-introspection-devel
BuildRequires:  gtk3-devel
BuildRequires:  gtk-layer-shell-devel
BuildRequires:  gtk4-devel
BuildRequires:  gtk4-layer-shell-devel

# Bundled dependency vendored via node_modules
Provides:       bundled(gnim)

%description
%{summary}.

%prep
%autosetup -n ags-%{commit} -p1

%build
npm install
%meson --prefix=%{_prefix}
%meson_build

%install
%meson_install

%files
%license LICENSE
%doc README.md
%doc examples/
%{_bindir}/ags
%{_datadir}/ags/

%changelog
%autochangelog
