import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Header,
  HeaderContainer,
  HeaderMenuButton,
  HeaderName,
  HeaderGlobalBar,
  HeaderGlobalAction,
  SkipToContent,
  SideNav,
  SideNavItems,
  SideNavLink,
  Content,
  Theme,
} from '@carbon/react';
import {
  Notification,
  Settings,
  Dashboard as DashboardIcon,
  WarningAltFilled,
  Activity,
} from '@carbon/icons-react';
import DashboardPage from './pages/Dashboard';

const POLL_INTERVAL_MS = 3000;

export default function App() {
  const [data,   setData]   = useState([]);
  const timerRef = useRef(null);
  const lastText = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/log/dashboard_log.json');
      if (!res.ok) return;
      const text = await res.text();
      if (text === lastText.current) return;
      lastText.current = text;
      const lines   = text.split('\n').filter(Boolean);
      const entries = lines
        .slice(-200)
        .map((l) => { try { return JSON.parse(l); } catch { return null; } })
        .filter(Boolean);
      setData(entries);
    } catch {
      // ignore network errors in the poll loop
    }
  }, []);

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, POLL_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [fetchData]);

  return (
    <Theme theme="g90">
      <HeaderContainer
        render={({ isSideNavExpanded, onClickSideNavExpand }) => (
          <>
            <Header aria-label="Zone Safety Command Center">
              <SkipToContent />
              <HeaderMenuButton
                aria-label={isSideNavExpanded ? 'Close menu' : 'Open menu'}
                onClick={onClickSideNavExpand}
                isActive={isSideNavExpanded}
                aria-expanded={isSideNavExpanded}
              />
              <HeaderName href="#" prefix="">
                Zone Safety Command Center
              </HeaderName>
              <HeaderGlobalBar>
                <HeaderGlobalAction aria-label="Notifications" onClick={() => {}}>
                  <Notification size={20} />
                </HeaderGlobalAction>
                <HeaderGlobalAction aria-label="Settings" onClick={() => {}}>
                  <Settings size={20} />
                </HeaderGlobalAction>
              </HeaderGlobalBar>
              <SideNav
                aria-label="Side navigation"
                expanded={isSideNavExpanded}
                isPersistent={false}
                onSideNavBlur={onClickSideNavExpand}
              >
                <SideNavItems>
                  <SideNavLink renderIcon={DashboardIcon} isActive href="#">
                    Overview
                  </SideNavLink>
                  <SideNavLink renderIcon={WarningAltFilled} href="#">
                    Critical Alerts
                  </SideNavLink>
                  <SideNavLink renderIcon={Activity} href="#">
                    Zone Monitoring
                  </SideNavLink>
                </SideNavItems>
              </SideNav>
            </Header>
            <Content className="page-content">
              <DashboardPage data={data} />
            </Content>
          </>
        )}
      />
    </Theme>
  );
}
