Name:           hyprsysteminfo
Version:        0.2.0
Release:        %autorelease -b1
Summary:        An application to display information about the running system
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsysteminfo
Source:         %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
Source1:        https://github.com/stephenberry/glaze/archive/v6.1.0/glaze-6.1.0.tar.gz

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch:    %{ix86}

BuildRequires:  cmake
BuildRequires:  desktop-file-utils
BuildRequires:  gcc-c++

BuildRequires:  qt6-qtbase-gui
BuildRequires:  qt6-qtbase
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-qtbase-private-devel
BuildRequires:  wayland-devel
BuildRequires:  pkgconfig(hyprutils)

Requires:       /usr/bin/lscpu
Requires:       /usr/bin/lspci
Requires:       /usr/bin/free
Requires:       hyprland-qt-support%{?_isa}

%description
A tiny qt6/qml application to display information about the running system,
or copy diagnostics data, without the terminal.

%prep
%autosetup -p1
tar -xf %{SOURCE1}

%build
%cmake -DCMAKE_BUILD_TYPE=Release -DGLAZE_SOURCE_DIR=%{_builddir}/glaze-6.1.0
%cmake_build

%install
%cmake_install

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/*.desktop

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop

%changelog
%autochangelog
