// Isolate the Windows process and MSVC filesystem boundaries from OpenSCAD.
#include <windows.h>
#include <mbctype.h>

#include <clocale>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <string>
#include <string_view>
#include <system_error>

namespace fs = std::filesystem;

template <typename Char>
void hex_units(const char *name, std::basic_string_view<Char> value)
{
  std::cout << name << '=' << std::hex << std::setfill('0');
  for (const auto unit : value) {
    std::cout << ' ' << std::setw(sizeof(Char) * 2)
              << (static_cast<unsigned>(unit) & (sizeof(Char) == 1 ? 0xff : 0xffff));
  }
  std::cout << std::dec << '\n';
}

[[noreturn]] void throw_win32(const char *operation)
{
  throw std::system_error(GetLastError(), std::system_category(), operation);
}

std::string to_utf8(std::wstring_view value)
{
  if (value.empty()) return {};
  const auto length = static_cast<int>(value.size());
  const auto size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
                                       value.data(), length, nullptr, 0, nullptr, nullptr);
  if (!size) throw_win32("WideCharToMultiByte(size)");
  std::string result(size, '\0');
  if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
                           value.data(), length, result.data(), size, nullptr, nullptr)) {
    throw_win32("WideCharToMultiByte(convert)");
  }
  return result;
}

template <typename Check>
bool stage(const char *name, Check check)
{
  std::cout << "begin " << name << '\n';
  try {
    const bool passed = check();
    std::cout << "end " << name << " result=" << passed << '\n';
    return passed;
  } catch (const std::system_error& error) {
    std::cout << "exception " << name << " code=" << error.code().value()
              << " category=" << error.code().category().name() << " what=" << error.what() << '\n';
  } catch (const std::exception& error) {
    std::cout << "exception " << name << " what=" << error.what() << '\n';
  } catch (...) {
    std::cout << "exception " << name << " unknown\n";
  }
  return false;
}

int wmain(int argc, wchar_t **argv)
{
  std::cout << std::unitbuf << std::boolalpha;
  std::cout << "acp=" << GetACP() << " console_cp=" << GetConsoleCP()
            << " console_output_cp=" << GetConsoleOutputCP()
            << " crt_mbcp=" << _getmbcp() << " crt_locale=" << std::setlocale(LC_CTYPE, nullptr) << '\n';
  if (argc != 2) return 2;

  const std::wstring_view argument(argv[1]);
  hex_units("argv_utf16", argument);
  std::string utf8;
  const bool converted = stage("argv_to_utf8", [&] {
    utf8 = to_utf8(argument);
    hex_units("argv_utf8", std::string_view(utf8));
    return !utf8.empty();
  });
  fs::path wide;
  const bool wide_ok = stage("filesystem_wide", [&] {
    wide = fs::path(argument);
    return fs::is_directory(wide);
  });
  const bool u8_ok = stage("filesystem_u8path", [&] {
    if (!converted) return false;
    const auto path = fs::u8path(utf8);
    hex_units("u8path_native_utf16", std::wstring_view(path.native()));
    return fs::is_directory(path) && path == wide;
  });
  const bool win32_env_ok = stage("win32_wide_environment", [&] {
    const DWORD size = GetEnvironmentVariableW(L"OPENSCADPATH", nullptr, 0);
    if (!size) throw_win32("GetEnvironmentVariableW(size)");
    std::wstring value(size, L'\0');
    const DWORD length = GetEnvironmentVariableW(L"OPENSCADPATH", value.data(), size);
    if (!length || length >= size) throw_win32("GetEnvironmentVariableW(read)");
    value.resize(length);
    hex_units("win32_environment_utf16", std::wstring_view(value));
    return value == argument;
  });
  const bool wide_env_ok = stage("crt_wide_environment", [&] {
    const auto *environment = _wgetenv(L"OPENSCADPATH");
    if (!environment) return false;
    hex_units("crt_wide_environment_utf16", std::wstring_view(environment));
    return argument == environment;
  });
  stage("crt_narrow_environment", [&] {
    const auto *environment = std::getenv("OPENSCADPATH");
    if (!environment) return false;
    hex_units("crt_narrow_environment_bytes", std::string_view(environment));
    return converted && utf8 == environment;
  });
  stage("filesystem_narrow_constructor", [&] {
    if (!converted) return false;
    const fs::path ordinary(utf8);
    hex_units("ordinary_native_utf16", std::wstring_view(ordinary.native()));
    return fs::is_directory(ordinary) && ordinary == wide;
  });
  const bool wide_utf8_ok = stage("filesystem_wide_to_utf8", [&] {
    if (!wide_ok) return false;
    const auto value = wide.generic_u8string();
    hex_units("generic_utf8", std::u8string_view(value));
    return std::string(value.begin(), value.end()) == to_utf8(wide.generic_wstring());
  });
  stage("filesystem_wide_to_narrow", [&] {
    if (!wide_ok) return false;
    const auto value = wide.generic_string();
    hex_units("generic_narrow", std::string_view(value));
    return value == to_utf8(wide.generic_wstring());
  });
  return !(converted && wide_ok && u8_ok && win32_env_ok && wide_env_ok && wide_utf8_ok);
}
