import Control.Monad (mapM_, filterM)
import Data.List (isSuffixOf)
import System.Directory (setCurrentDirectory, getDirectoryContents,
  removeFile, doesFileExist)
import System.Environment (getArgs)
import System.Exit (exitWith, ExitCode(ExitFailure))
import System.IO (hPutStrLn, stderr)
import System.Posix.Files (getFileStatus, statusChangeTime)
import Foreign.C.Types (CTime(..))

-- pkgdir = "/home/repo"
pkgdir = "/mnt/data/repo"
-- pkgdir = "/home/lilydjwg/tmpfs/repo"
exts = [".pkg.tar.xz", ".pkg.tar.xz.sig"]

olderThan t f = do
  st <- getFileStatus f
  return $ (statusChangeTime st) < (CTime t)

removepkg t = do
  setCurrentDirectory pkgdir
  getDirectoryContents "." >>= filterM doesFileExist . filter extOk
  >>= filterM (olderThan (read t)) >>= mapM_ verboseRemove
    where verboseRemove f = do putStrLn ("removing " ++ f ++ ".")
                               removeFile f
          extOk f = any (`isSuffixOf` f) exts

main = do
  args <- getArgs
  case args of
    ["I'm sure!", t] -> removepkg t
    _ -> hPutStrLn stderr "No, I won't do that." >> exitWith (ExitFailure 1)
