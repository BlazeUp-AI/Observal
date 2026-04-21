import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { RegistrySidebar } from "@/components/nav/registry-sidebar";
import { CommandMenu } from "@/components/nav/command-menu";
import { Toaster } from "@/components/ui/sonner";
import { AuthGuard } from "@/components/layouts/auth-guard";
import { RoleGuard } from "@/components/layouts/role-guard";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <RoleGuard minRole="reviewer">
        <SidebarProvider>
          <RegistrySidebar />
          <SidebarInset>{children}</SidebarInset>
          <CommandMenu />
          <Toaster visibleToasts={1} />
        </SidebarProvider>
      </RoleGuard>
    </AuthGuard>
  );
}
