// Isolate the Windows process and MSVC filesystem boundaries from OpenSCAD.
#include <windows.h>

#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <filesystem>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

std::string to_utf8(const wchar_t *value)
{
  const auto length = static_cast<int>(std::wcslen(value));
  const auto size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
                                       value, length, nullptr, 0, nullptr, nullptr);
  std::string result(size, '\0');
  if (size) WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
                                value, length, result.data(), size, nullptr, nullptr);
  return result;
}

int wmain(int argc, wchar_t **argv)
{
  if (argc != 2) return 2;
  const auto utf8 = to_utf8(argv[1]);
  const fs::path wide(argv[1]);
  const auto decoded = fs::u8path(utf8);
  const auto *environment = _wgetenv(L"OPENSCADPATH");
  const auto *narrow_environment = std::getenv("OPENSCADPATH");
  std::cout << std::boolalpha
            << "acp=" << GetACP() << '\n'
            << "utf16_units=" << std::wcslen(argv[1]) << '\n'
            << "utf8_bytes=" << utf8.size() << '\n'
            << "wide_exists=" << fs::is_directory(wide) << '\n'
            << "u8path_exists=" << fs::is_directory(decoded) << '\n'
            << "u8path_matches_wide=" << (decoded == wide) << '\n'
            << "wide_environment_matches=" << (environment && wide == fs::path(environment)) << '\n'
            << "narrow_environment_bytes=" << (narrow_environment ? std::strlen(narrow_environment) : 0) << '\n'
            << "narrow_environment_matches_utf8=" << (narrow_environment && utf8 == narrow_environment) << '\n';
  try {
    const fs::path ordinary(utf8);
    std::cout << "ordinary_path_exists=" << fs::is_directory(ordinary) << '\n'
              << "ordinary_path_matches_wide=" << (ordinary == wide) << '\n';
  } catch (const fs::filesystem_error& error) {
    std::cout << "ordinary_path_error_code=" << error.code().value() << '\n';
  }
  try {
    std::cout << "wide_to_narrow_matches_utf8=" << (wide.generic_string() == to_utf8(wide.generic_wstring().c_str())) << '\n';
  } catch (const fs::filesystem_error& error) {
    std::cout << "\nwide_to_narrow_error_code=" << error.code().value() << '\n';
  }
  return !environment || wide != fs::path(environment) || !fs::is_directory(wide) || decoded != wide;
}
